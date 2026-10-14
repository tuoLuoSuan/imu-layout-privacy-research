package org.imulayout.recorder;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.hardware.*;
import android.os.*;
import org.json.*;
import java.io.File;
import java.util.UUID;
import org.imulayout.recorder.core.*;
import static org.imulayout.recorder.AndroidRecordingRuntime.now;

public final class RecorderService extends Service implements SensorEventListener {
    public static final String EXTRA_RATE_HZ="requested_rate_hz";
    private RecordingConfig config;
    private OperationGate.Lease operation;
    private static volatile RecorderService current;
    private static volatile SessionFiles lastWriter;
    private static volatile String message="尚未开始";
    private static volatile boolean uiVisible;
    private HandlerThread controlThread,callbackThread;
    private Handler control;
    private AndroidRecordingRuntime runtime;
    private volatile SessionController controller;
    private SessionFiles files;
    private final WakeLeasePolicy lease=new WakeLeasePolicy();
    private final JSONArray leaseEvents=new JSONArray(),states=new JSONArray(),notificationEvents=new JSONArray();
    private JSONObject metadata;
    private Sensor accel,gyro;
    private boolean startRequested,unregistered,finalized;
    private long nextAnchor,nextObservation,unregisterNs;
    private String state="unknown",startError="";
    public static boolean busy(){SessionFiles f=lastWriter;return current!=null || (f!=null&&!f.finished);}
    public static boolean running(){return current!=null;}
    public static int requestedRateHz(){RecorderService s=current;return s==null||s.config==null?-1:s.config.requestedRateHz;}
    public static String summary() {
        RecorderService s=current;
        if(s==null || s.controller==null || !s.controller.started)return message;
        SessionController c=s.controller;
        synchronized(c){return message+"\n时长 "+Math.max(0,((c.stopping?c.stopNs:now())-c.startNs)/1_000_000_000L)+" 秒\n加速度 "+c.received[0]+" 条 · 角速度 "+c.received[1]+" 条";}
    }
    public static void uiState(boolean foreground) {
        uiVisible=foreground;RecorderService s=current;if(s!=null)s.control.post(s::updateState);
    }
    private final BroadcastReceiver receiver=new BroadcastReceiver(){@Override public void onReceive(Context c,Intent i){
        control.post(()->{if(files!=null)files.event("system_broadcast",Jsons.object("action",i.getAction(),"observation",runtime.powerObservation()));updateState();});
    }};
    @Override public void onCreate() {
        super.onCreate();current=this;
        controlThread=new HandlerThread("imu-control");controlThread.start();control=new Handler(controlThread.getLooper());
        callbackThread=new HandlerThread("imu-callback",android.os.Process.THREAD_PRIORITY_MORE_FAVORABLE);callbackThread.start();
        runtime=new AndroidRecordingRuntime(this);AndroidRecordingRuntime.createChannel(this);
        IntentFilter filter=new IntentFilter();for(String a:new String[]{Intent.ACTION_SCREEN_ON,Intent.ACTION_SCREEN_OFF,Intent.ACTION_USER_PRESENT,Intent.ACTION_POWER_CONNECTED,Intent.ACTION_POWER_DISCONNECTED})filter.addAction(a);
        registerReceiver(receiver,filter,Context.RECEIVER_NOT_EXPORTED);
    }
    @Override public int onStartCommand(Intent intent,int flags,int id) {
        if(intent!=null && "stop".equals(intent.getAction())) {
            control.post(()->{if(controller!=null)controller.requestStop(intent.getBooleanExtra("user_button",false)?"user":"notification",now());else stopSelf();});return START_NOT_STICKY;
        }
        if(startRequested)return START_NOT_STICKY;
        startRequested=true;
        try {
            if(lastWriter!=null&&!lastWriter.finished)throw new IllegalStateException("上一条记录尚未关闭");
            config=RecordingConfig.of(intent==null?RecordingConfig.DEFAULT_RATE_HZ:intent.getIntExtra(EXTRA_RATE_HZ,RecordingConfig.DEFAULT_RATE_HZ));
            operation=OperationGate.SESSIONS.tryAcquire();
            if(operation==null)throw new IllegalStateException("记录操作尚未结束，请稍后重试");
            if(!AndroidRecordingRuntime.notificationAllowed(this))throw new IllegalStateException("通知未获允许");
            startForeground(AndroidRecordingRuntime.NOTIFICATION_ID,AndroidRecordingRuntime.notification(this,"正在初始化"),ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            message="启动中";control.post(this::initialize);
        } catch(Exception e){message="启动失败："+e.getMessage();saveStartupFailure(e);stopSelf();}
        return START_NOT_STICKY;
    }
    private void saveStartupFailure(Exception e) {
        try {Jsons.save(new File(getFilesDir(),"last_start_failure.json"),Jsons.object("wall_ms",System.currentTimeMillis(),"elapsed_ns",now(),"exception",e.toString(),"type_fallback_attempted",false));}catch(Exception ignored){}
    }
    private void initialize() {
        try {
            File dir=new File(new File(getFilesDir(),"sessions"),UUID.randomUUID().toString());
            if(!dir.mkdirs())throw new IllegalStateException("无法建立会话目录");
            metadata=Jsons.object("format_version",1,"session_id",dir.getName(),"app_version",BuildConfig.VERSION_NAME,"source_digest",BuildConfig.SOURCE_DIGEST,
                "sdk_int",Build.VERSION.SDK_INT,"target_sdk",getApplicationInfo().targetSdkVersion,"device",Build.MANUFACTURER+" "+Build.MODEL,"build_fingerprint",Build.FINGERPRINT,
                "requested_rate_hz",config.requestedRateHz,"requested_period_us",config.periodUs,"requested_max_latency_us",0,"fgs_type","specialUse","completion_state","incomplete","start_wall_ms",System.currentTimeMillis());
            Jsons.save(new File(dir,"state.json"),Jsons.object("state","initializing"));
            files=new SessionFiles(dir,AndroidRecordingRuntime::now,this::fault);lastWriter=files;files.start();
            controller=new SessionController(files::offer,reason->control.post(this::beginStop));
            files.event("foreground_promotion_returned",Jsons.object("type","specialUse","external_confirmation",false));
            accel=runtime.sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER,false);gyro=runtime.sensors.getDefaultSensor(Sensor.TYPE_GYROSCOPE,false);
            if(accel==null || gyro==null || accel.isWakeUpSensor() || gyro.isWakeUpSensor())throw new IllegalStateException("缺少所需的非唤醒原始传感器");
            config.validateSensor("含重力加速度",accel.getMinDelay(),accel.getMaxDelay());
            config.validateSensor("角速度",gyro.getMinDelay(),gyro.getMaxDelay());
            metadata.put("sensors",new JSONArray().put(AndroidRecordingRuntime.sensorInfo(accel)).put(AndroidRecordingRuntime.sensorInfo(gyro)));
            metadata.put("units",Jsons.object("accelerometer","m/s^2 including gravity","gyroscope","rad/s"));
            if(!acquireLease())throw new IllegalStateException("唤醒锁申请失败");
            long before=now();Handler callback=new Handler(callbackThread.getLooper());
            boolean a=runtime.sensors.registerListener(this,accel,config.periodUs,0,callback),g=runtime.sensors.registerListener(this,gyro,config.periodUs,0,callback);
            long after=now();files.event("register_returned",Jsons.object("before_ns",before,"after_ns",after,"accelerometer",a,"gyroscope",g));
            if(!a||!g)throw new IllegalStateException("传感器注册失败");
            controller.start(now());metadata.put("collection_start_elapsed_ns",controller.startNs);metadata.put("planned_stop_elapsed_ns",controller.startNs+RecordingContract.MAX_DURATION_NS);
            updateState();anchor(controller.startNs);observe();nextAnchor=controller.startNs+10_000_000_000L;nextObservation=nextAnchor;
            Jsons.save(new File(dir,"metadata.json"),metadata);Jsons.save(new File(dir,"state.json"),Jsons.object("state","collecting"));
            message="正在采集";control.postDelayed(this::tick,1000);
        } catch(Exception e) {
            startError=e.toString();message="启动失败："+e.getMessage();saveStartupFailure(e);
            if(controller!=null)controller.requestStop("start_failure",now());else {if(files!=null)files.requestClose();releaseLease();stopSelf();}
        }
    }
    private boolean acquireLease() {
        long before=now();String error="";
        try{runtime.wakeLock.acquire(60_000L);}catch(Exception e){error=e.toString();}
        long after=now();long old=lease.deadline();boolean held=runtime.wakeLock.isHeld();
        String failure=lease.acquired(before,after,held && error.isEmpty());
        JSONObject event=Jsons.object("before_ns",before,"after_ns",after,"previous_deadline_ns",old,"requested_ms",60000,
            "planned_renew_ns",old==0?before:old-40_000_000_000L,"logical_deadline_ns",lease.deadline(),"is_held",held,"exception",error,"result",failure==null?"ok":failure);
        leaseEvents.put(event);if(files!=null)files.event("wake_lock_acquire",event);return failure==null;
    }
    private void releaseLease() {
        boolean before=runtime.wakeLock.isHeld();String error="";
        try{if(before)runtime.wakeLock.release();}catch(Exception e){error=e.toString();}
        leaseEvents.put(Jsons.object("operation","release","elapsed_ns",now(),"was_held",before,"is_held_after",runtime.wakeLock.isHeld(),"exception",error));
    }
    private void tick() {
        try {tickControl();}catch(Exception e){startError=e.toString();fault("control_failure");}
    }
    private void tickControl() {
        if(finalized || controller==null)return;
        long t=now();controller.tick(t);
        String failure=lease.check(t,runtime.wakeLock.isHeld());
        if(failure!=null)fault(failure);else if(lease.renewDue(t) && !acquireLease())fault("wake_lock_coverage_lost");
        if(t>=nextAnchor){anchor(nextAnchor);nextAnchor=t+10_000_000_000L;}
        if(t>=nextObservation){observe();nextObservation=t+10_000_000_000L;}
        if(!finalized)control.postDelayed(this::tick,1000);
    }
    private void anchor(long planned){long before=now(),wall=System.currentTimeMillis(),after=now();if(files!=null)files.anchor(planned,before,wall,after);}
    private void observe() {
        JSONObject n=runtime.notificationObservation();notificationEvents.put(Jsons.object("elapsed_ns",now(),"observation",n));
        if(files!=null)files.event("runtime_observation",Jsons.object("notification",n,"power",runtime.powerObservation()));
        if(!AndroidRecordingRuntime.notificationAllowed(this)){if(metadata!=null)try{metadata.put("visibility_condition_failed",true);}catch(JSONException ignored){}fault("visibility_condition_failed");}
        else if(controller!=null && controller.started) {
            String text=controller.stopping?"正在收尾，请等待保存":"已采集 "+Math.max(0,(now()-controller.startNs)/1_000_000_000L)+" 秒";
            try{getSystemService(NotificationManager.class).notify(AndroidRecordingRuntime.NOTIFICATION_ID,AndroidRecordingRuntime.notification(this,text));}
            catch(Exception e){startError=e.toString();fault("notification_update_failure");}
        }
        updateState();
    }
    private void updateState() {
        if(controller==null || !controller.started || controller.stopping)return;
        String next=!getSystemService(PowerManager.class).isInteractive()?"screen_off":uiVisible?"foreground":"other_app";
        if(!state.equals(next)){state=next;JSONObject e=Jsons.object("elapsed_ns",now(),"state",state);states.put(e);files.event("state_observed",e);}
    }
    private void fault(String reason) {
        control.post(()->{if(controller==null)return;if(controller.stopping){controller.abnormal=true;if(controller.stopFailure.isEmpty())controller.stopFailure=reason;}
            else controller.requestStop(reason,now());});
    }
    @Override public void onSensorChanged(SensorEvent e) {
        long received=now();SessionController c=controller;if(c==null)return;
        if(c.stopping)return;
        String failure=lease.check(received,runtime.wakeLock.isHeld());
        if(failure!=null){c.requestStop(failure,received);return;}
        if(e.values.length<3){c.requestStop("invalid_sensor_values",received);return;}
        c.onSensorSample(e.sensor==accel?0:1,e.timestamp,received,e.values[0],e.values[1],e.values[2],e.accuracy);
    }
    @Override public void onAccuracyChanged(Sensor sensor,int accuracy){if(files!=null)files.event("accuracy",Jsons.object("type",sensor.getType(),"status",accuracy));}
    private void beginStop() {
        if(unregistered)return;unregistered=true;message="正在收尾";
        try{runtime.sensors.unregisterListener(this);}catch(Exception e){controller.abnormal=true;controller.stopFailure="unregister_failure";startError=e.toString();}
        unregisterNs=now();
        anchor(now());files.event("unregistered",Jsons.object("request_ns",controller.stopNs,"actual_ns",unregisterNs,"reason",controller.stoppedReason));files.requestClose();
        control.postDelayed(this::monitorDrain,100);
    }
    private void monitorDrain() {
        if(finalized)return;
        controller.tick(now());
        if(files.finished){complete();return;}
        if(controller.stopFailure.equals("drain_timeout")) {
            finalized=true;message="收尾超时，部分文件保留；关闭完成后可恢复导出";releaseLease();
            try{metadata.put("stop_failure","drain_timeout");metadata.put("completion_state","aborted");Jsons.save(new File(files.dir,"metadata.json"),metadata);}catch(Exception ignored){}
            stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();return;
        }
        control.postDelayed(this::monitorDrain,100);
    }
    private void complete() {
        finalized=true;
        try {
            boolean counts=true;for(int c=0;c<2;c++)counts &= controller.received[c]==files.confirmed[c] && controller.dropped[c]==0;
            controller.finish(files.error==null && files.closedOk && counts);
            releaseLease();
            metadata.put("completion_state",controller.abnormal?"aborted":"complete");metadata.put("stopped_reason",controller.stoppedReason);metadata.put("stop_failure",controller.stopFailure);
            metadata.put("collection_start_elapsed_ns",controller.startNs);metadata.put("stop_elapsed_ns",controller.stopNs);metadata.put("unregister_elapsed_ns",unregisterNs);
            metadata.put("max_duration_stop_lateness_ns",controller.stoppedReason.equals("max_duration")?Math.max(0,controller.stopNs-controller.startNs-RecordingContract.MAX_DURATION_NS):0);
            metadata.put("closed_elapsed_ns",now());metadata.put("received",Jsons.longs(controller.received));metadata.put("enqueued",Jsons.longs(controller.enqueued));metadata.put("dropped",Jsons.longs(controller.dropped));
            metadata.put("written",Jsons.longs(files.written));metadata.put("confirmed",Jsons.longs(files.confirmed));metadata.put("queue_peak",files.queuePeak);metadata.put("outside_gate_callbacks",controller.outsideGate);
            metadata.put("last_successful_csv_sync_elapsed_ns",Jsons.longs(files.successfulSyncTimes()));
            metadata.put("states",states);metadata.put("wake_lock_operations",leaseEvents);metadata.put("notification_observations",notificationEvents);metadata.put("storage_error",files.error==null?JSONObject.NULL:files.error);metadata.put("start_error",startError);
            JSONArray mtimes=new JSONArray();for(String c:RecordingContract.CHANNELS)mtimes.put(Jsons.object("file",c+".csv","mtime_wall_ms",new File(files.dir,c+".csv").lastModified()));metadata.put("source_mtimes",mtimes);
            if(!files.closedOk)throw new IllegalStateException("文件关闭未确认，须下次恢复");
            SessionExporter.seal(files.dir,metadata);
            String failure=controller.stopFailure.isEmpty()?controller.stoppedReason:controller.stopFailure;
            String explanation=failure.equals("wake_lock_coverage_lost")?"连续运行条件中断":failure.equals("queue_overflow")?"写入缓冲不足":failure.equals("visibility_condition_failed")?"采集通知条件不满足":"采集发生异常";
            message=controller.abnormal?"未完整结束："+explanation+"\n部分记录已保留，可导出":"已保存，可导出；连续性结论请查看完整性报告";
        } catch(Exception e){message="收尾失败，原文件保留："+e.getMessage();saveStartupFailure(e);}
        stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();
    }
    @Override public void onDestroy() {
        if(!finalized && controller!=null){controller.requestStop("service_destroyed",now());runtime.sensors.unregisterListener(this);if(files!=null)files.requestClose();releaseLease();message="采集中断，部分文件保留";}
        try{unregisterReceiver(receiver);}catch(Exception ignored){}
        if(current==this)current=null;
        OperationGate.Lease finishedOperation=operation;SessionFiles writer=files;
        if(finishedOperation!=null) {
            if(writer==null||writer.finished)finishedOperation.release();
            else new Thread(()->{try{writer.worker.join();finishedOperation.release();}catch(InterruptedException ignored){Thread.currentThread().interrupt();}},"imu-close-guard").start();
        }
        callbackThread.quitSafely();controlThread.quitSafely();super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent){return null;}
}
