package org.imulayout.recorder;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.*;
import java.io.*;
import java.text.NumberFormat;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.imulayout.recorder.ui.RecorderPresentation;
import org.imulayout.recorder.ui.RecorderPresentation.Phase;
import org.imulayout.recorder.ui.SessionEntry;
import org.imulayout.recorder.ui.FrequencyDialog;
import org.imulayout.recorder.core.RecordingConfig;
import org.imulayout.recorder.core.OperationGate;
import org.imulayout.recorder.core.SessionDeletion;

/** User interface only. Sensor collection, files and acceptance rules live elsewhere. */
public final class MainActivity extends Activity {
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private final NumberFormat numbers=NumberFormat.getIntegerInstance(Locale.CHINA);
    private TextView status,duration,accelCount,gyroCount,collectHint,recordsHint,recordCount;
    private Button primaryAction,export,navCollect,navRecords,frequency,deleteRecord,retryCleanup;
    private View collectPage,recordsPage,emptyRecords;
    private LinearLayout recordList;
    private List<SessionEntry> entries=new ArrayList<>();
    private volatile boolean working;
    private boolean exporting,deleting,wasBusy,active,recordsVisible,startPending,stopPending,refreshNeeded=true,hasPendingCleanup;
    private String selectedId="";
    private File pendingExport;
    private OperationGate.Lease exportOperation;
    private RecordingConfig selectedConfig;
    private Phase lastPhase;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        AndroidRecordingRuntime.createChannel(this);
        try{selectedConfig=RecordingConfig.of(getSharedPreferences("recorder_settings",MODE_PRIVATE).getInt("requested_rate_hz",100));}
        catch(IllegalArgumentException e){selectedConfig=RecordingConfig.of(100);}
        if(saved!=null) {
            selectedId=saved.getString("selected_record","");
            recordsVisible=saved.getBoolean("records_visible",false);
            String pending=saved.getString("export_session","");
            if(pending.matches("[a-zA-Z0-9_-]+"))pendingExport=new File(new File(getFilesDir(),"sessions"),pending);
            exportOperation=OperationGate.SESSIONS.find(saved.getString("export_operation",""));
        }
        setContentView(R.layout.activity_main);
        status=findViewById(R.id.status);duration=findViewById(R.id.duration);
        accelCount=findViewById(R.id.accel_count);gyroCount=findViewById(R.id.gyro_count);
        collectHint=findViewById(R.id.collect_hint);recordsHint=findViewById(R.id.records_hint);
        recordCount=findViewById(R.id.record_count);
        primaryAction=findViewById(R.id.primary_action);export=findViewById(R.id.export);
        frequency=findViewById(R.id.frequency);deleteRecord=findViewById(R.id.delete_record);retryCleanup=findViewById(R.id.retry_cleanup);
        navCollect=findViewById(R.id.nav_collect);navRecords=findViewById(R.id.nav_records);
        collectPage=findViewById(R.id.collect_page);recordsPage=findViewById(R.id.records_page);
        recordList=findViewById(R.id.record_list);emptyRecords=findViewById(R.id.empty_records);
        ((TextView)findViewById(R.id.version)).setText(getString(R.string.version_label,BuildConfig.VERSION_NAME));
        primaryAction.setOnClickListener(v->primaryClick());
        export.setOnClickListener(v->chooseExport());
        frequency.setOnClickListener(v->editFrequency());deleteRecord.setOnClickListener(v->confirmDelete());
        retryCleanup.setOnClickListener(v->changeRecords(null));
        navCollect.setOnClickListener(v->showPage(false));navRecords.setOnClickListener(v->showPage(true));
        showPage(recordsVisible);
        View root=findViewById(R.id.root);
        root.setOnApplyWindowInsetsListener((v,insets)->{
            Insets safe=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());
            v.setPadding(safe.left,safe.top,safe.right,safe.bottom);return insets;
        });
        root.requestApplyInsets();
        WindowInsetsController bars=getWindow().getInsetsController();
        if(bars!=null) {
            int light=WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
            bars.setSystemBarsAppearance(light,light);
        }
    }

    private void showPage(boolean records) {
        recordsVisible=records;
        collectPage.setVisibility(records?View.GONE:View.VISIBLE);
        recordsPage.setVisibility(records?View.VISIBLE:View.GONE);
        navCollect.setSelected(!records);navRecords.setSelected(records);
        navCollect.setCompoundDrawableTintList(ColorStateList.valueOf(getColor(records?R.color.muted:R.color.accent)));
        navRecords.setCompoundDrawableTintList(ColorStateList.valueOf(getColor(records?R.color.accent:R.color.muted)));
    }
    private void primaryClick() {
        if(working||startPending||stopPending)return;
        RecorderPresentation p=RecorderPresentation.from(RecorderService.summary(),RecorderService.busy(),RecorderService.running());
        if(p.canStop) {
            stopPending=true;update();
            try {startService(new Intent(this,RecorderService.class).setAction("stop").putExtra("user_button",true));}
            catch(Exception e){stopPending=false;update();collectHint.setText(getString(R.string.stop_failed,e.getMessage()));}
        } else if(p.canStart)begin();
    }
    private void begin() {
        if(RecorderService.busy()||working||startPending||pendingExport!=null||OperationGate.SESSIONS.isHeld())return;
        if(checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},10);return;
        }
        if(!AndroidRecordingRuntime.notificationAllowed(this)) {
            collectHint.setText(R.string.notification_needed);
            startActivity(new Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE,getPackageName()).putExtra(Settings.EXTRA_CHANNEL_ID,AndroidRecordingRuntime.CHANNEL));return;
        }
        try {
            startPending=true;
            RecordingConfig sessionConfig=selectedConfig;
            startForegroundService(new Intent(this,RecorderService.class).setAction("start").putExtra(RecorderService.EXTRA_RATE_HZ,sessionConfig.requestedRateHz));update();
            ui.postDelayed(()->{
                if(!isDestroyed()&&startPending&&!RecorderService.busy()) {
                    startPending=false;update();collectHint.setText(R.string.hint_start_not_observed);
                }
            },5000);
        } catch(Exception e){startPending=false;update();collectHint.setText(getString(R.string.start_failed,e.getMessage()));}
    }
    private void editFrequency() {
        if(working||RecorderService.busy()||startPending||stopPending||pendingExport!=null||OperationGate.SESSIONS.isHeld())return;
        FrequencyDialog.show(this,selectedConfig,config->{
            if(working||RecorderService.busy()||startPending||OperationGate.SESSIONS.isHeld())throw new IllegalArgumentException(getString(R.string.operation_busy));
            selectedConfig=config;getSharedPreferences("recorder_settings",MODE_PRIVATE).edit().putInt("requested_rate_hz",config.requestedRateHz).apply();update();
        });
    }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] grants) {
        super.onRequestPermissionsResult(request,permissions,grants);
        if(request==10)collectHint.setText(grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED
            ?R.string.notification_allowed:R.string.notification_denied);
    }

    private void refreshSessions() {
        if(working||RecorderService.busy()||pendingExport!=null){refreshNeeded=true;return;}
        OperationGate.Lease operation=OperationGate.SESSIONS.tryAcquire();
        if(operation==null){refreshNeeded=true;return;}
        refreshNeeded=false;
        working=true;recordCount.setText(R.string.records_loading);update();
        io.execute(()->{
            ArrayList<SessionEntry> found=new ArrayList<>();String error="";boolean pending=false;
            try {
                File root=new File(getFilesDir(),"sessions");SessionExporter.recover(root);
                File[] all=root.listFiles(f->f.isDirectory()&&!java.nio.file.Files.isSymbolicLink(f.toPath())&&new File(f,"manifest.json").isFile());
                if(all!=null)for(File d:all)found.add(SessionEntry.read(d));
                found.sort((a,b)->Long.compare(b.startWallMs,a.startWallMs));
                pending=new SessionDeletion(getFilesDir()).hasPending();
            } catch(Exception e){error=e.toString();}finally{operation.release();}
            String result=error;boolean pendingCleanup=pending;
            ui.post(()->{
                working=false;if(isDestroyed())return;entries=found;hasPendingCleanup=pendingCleanup;
                boolean retained=false;for(SessionEntry entry:entries)retained|=entry.directory.getName().equals(selectedId);
                if(!retained)selectedId=entries.isEmpty()?"":entries.get(0).directory.getName();
                renderRecords();
                if(!result.isEmpty())recordsHint.setText(getString(R.string.recovery_failed,result));
                else if(hasPendingCleanup)recordsHint.setText(R.string.cleanup_pending);
                update();
            });
        });
    }
    private void renderRecords() {
        recordList.removeAllViews();emptyRecords.setVisibility(entries.isEmpty()?View.VISIBLE:View.GONE);
        recordCount.setText(getString(R.string.records_count,entries.size()));
        SimpleDateFormat dates=new SimpleDateFormat("yyyy-MM-dd  HH:mm:ss",Locale.CHINA);
        for(SessionEntry entry:entries) {
            View row=getLayoutInflater().inflate(R.layout.row_record,recordList,false);
            row.setTag(entry.directory.getName());
            String date=dates.format(new Date(entry.startWallMs));
            String id=getString(R.string.record_id,entry.shortId);
            String quality=getString(R.string.record_status,entry.completionText,entry.qualityText);
            ((TextView)row.findViewById(R.id.record_date)).setText(date);
            ((TextView)row.findViewById(R.id.record_short_id)).setText(id);
            ((TextView)row.findViewById(R.id.record_frequency)).setText(entry.frequencyText);
            TextView badge=row.findViewById(R.id.record_quality);badge.setText(quality);
            badge.setTextColor(getColor(entry.needsAttention?R.color.warning:R.color.muted));
            row.setContentDescription(date+"，"+id+"，"+entry.frequencyText+"，"+quality);
            row.setAccessibilityDelegate(new View.AccessibilityDelegate(){
                @Override public void onInitializeAccessibilityNodeInfo(View host,AccessibilityNodeInfo info) {
                    super.onInitializeAccessibilityNodeInfo(host,info);
                    info.setClassName("android.widget.RadioButton");info.setCheckable(true);info.setChecked(host.isSelected());
                }
            });
            row.setOnClickListener(v->{selectedId=entry.directory.getName();updateSelection();recordsHint.setText(entry.readWarning);update();});
            LinearLayout.LayoutParams layout=(LinearLayout.LayoutParams)row.getLayoutParams();layout.bottomMargin=dp(10);
            recordList.addView(row,layout);
        }
        updateSelection();
    }
    private void updateSelection() {
        for(int i=0;i<recordList.getChildCount();i++) {
            View row=recordList.getChildAt(i);boolean selected=selectedId.equals(row.getTag());
            row.setSelected(selected);((RadioButton)row.findViewById(R.id.record_radio)).setChecked(selected);
        }
    }
    private SessionEntry selectedEntry() {
        for(SessionEntry entry:entries)if(entry.directory.getName().equals(selectedId))return entry;
        return null;
    }
    private void chooseExport() {
        SessionEntry entry=selectedEntry();
        if(entry==null||working||RecorderService.busy()||startPending||stopPending)return;
        exportOperation=OperationGate.SESSIONS.tryAcquire();if(exportOperation==null)return;
        pendingExport=entry.directory;
        Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/zip")
            .putExtra(Intent.EXTRA_TITLE,"imu_"+pendingExport.getName()+".zip");
        try{startActivityForResult(intent,20);update();}
        catch(Exception e){releaseExport();recordsHint.setText(getString(R.string.export_failed,e.getMessage()));update();}
    }
    private void releaseExport() {
        pendingExport=null;if(exportOperation!=null){exportOperation.release();exportOperation=null;}
    }
    @Override public void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request!=20)return;
        if(result!=RESULT_OK||data==null||data.getData()==null||pendingExport==null){releaseExport();refreshNeeded=true;update();return;}
        if(exportOperation==null)exportOperation=OperationGate.SESSIONS.tryAcquire();
        if(exportOperation==null||RecorderService.busy()){releaseExport();recordsHint.setText(R.string.operation_busy);update();return;}
        OperationGate.Lease operation=exportOperation;exportOperation=null;
        Uri uri=data.getData();File dir=pendingExport;pendingExport=null;working=true;exporting=true;
        recordsHint.setText(R.string.exporting);update();
        io.execute(()->{
            String text;
            try(OutputStream out=getContentResolver().openOutputStream(uri,"w")) {
                if(out==null)throw new IOException(getString(R.string.export_open_failed));
                SessionExporter.zip(dir,out);text=getString(R.string.export_success);
            } catch(Exception e) {
                text=getString(R.string.export_failed,e.getMessage());
                try {android.provider.DocumentsContract.deleteDocument(getContentResolver(),uri);}
                catch(Exception ignored){text+=getString(R.string.export_partial);}
            }finally{operation.release();}
            String message=text;
            ui.post(()->{working=false;exporting=false;if(!isDestroyed()){recordsHint.setText(message);update();}});
        });
    }

    private void confirmDelete() {
        SessionEntry entry=selectedEntry();
        if(entry==null||working||RecorderService.busy()||startPending||stopPending||pendingExport!=null||OperationGate.SESSIONS.isHeld())return;
        String date=new SimpleDateFormat("yyyy-MM-dd HH:mm:ss",Locale.CHINA).format(new Date(entry.startWallMs));
        new AlertDialog.Builder(this).setTitle(R.string.delete_title)
            .setMessage(getString(R.string.delete_confirmation,date,entry.shortId))
            .setNegativeButton(android.R.string.cancel,null)
            .setPositiveButton(R.string.delete_record,(dialog,which)->changeRecords(entry.directory.getName())).show();
    }
    private void changeRecords(String id) {
        if(working||RecorderService.busy()||startPending||stopPending||pendingExport!=null)return;
        OperationGate.Lease operation=OperationGate.SESSIONS.tryAcquire();if(operation==null)return;
        working=true;deleting=true;recordsHint.setText(R.string.deleting);update();
        io.execute(()->{
            String message;
            try {
                SessionDeletion store=new SessionDeletion(getFilesDir());
                if(id==null){store.retryPending();message=getString(R.string.cleanup_success);}
                else{store.delete(id);message=getString(R.string.delete_success);}
            }catch(Exception e){message=getString(id==null?R.string.cleanup_failed:R.string.delete_failed,e.getMessage());}
            finally{operation.release();}
            String result=message;
            ui.post(()->{working=false;deleting=false;if(!isDestroyed()){recordsHint.setText(result);refreshSessions();}});
        });
    }

    private void update() {
        boolean busy=RecorderService.busy(),running=RecorderService.running();
        RecorderPresentation p=RecorderPresentation.from(RecorderService.summary(),busy,running);
        if(busy)startPending=false;
        if(!running||p.phase==Phase.STOPPING)stopPending=false;
        Phase phase=startPending?Phase.STARTING:stopPending?Phase.STOPPING:p.phase;
        boolean attention=phase==Phase.ERROR||phase==Phase.INTERRUPTED||phase==Phase.UNKNOWN;
        setText(status,getString(titleFor(phase)));status.setTextColor(getColor(attention?R.color.warning:R.color.accent));
        status.setCompoundDrawablesRelativeWithIntrinsicBounds(attention?R.drawable.ic_warning:R.drawable.ic_dot,0,0,0);
        setText(duration,p.durationText());setText(accelCount,countText(p.accelerometer));setText(gyroCount,countText(p.gyroscope));
        if(phase!=lastPhase&&!working) {
            if(attention)collectHint.setText(p.detail.isEmpty()?getString(R.string.hint_interrupted):p.detail);
            else collectHint.setText(hintFor(phase));
            lastPhase=phase;
        }
        boolean pending=startPending||stopPending;
        boolean locked=OperationGate.SESSIONS.isHeld()||pendingExport!=null;
        primaryAction.setText(phase==Phase.STARTING?R.string.starting:phase==Phase.STOPPING?R.string.saving
            :p.canStop?R.string.stop_recording:R.string.start_recording);
        primaryAction.setEnabled(!working&&!pending&&(p.canStop||(p.canStart&&!locked)));
        int activeRate=RecorderService.requestedRateHz();
        frequency.setText(getString(activeRate>0?R.string.frequency_recording:R.string.frequency_current,activeRate>0?activeRate:selectedConfig.requestedRateHz));
        frequency.setEnabled(!busy&&!working&&!pending&&!locked);
        export.setText(exporting?R.string.exporting:R.string.export_zip);
        export.setEnabled(!busy&&!working&&!pending&&!locked&&selectedEntry()!=null);
        deleteRecord.setText(deleting?R.string.deleting:R.string.delete_record);
        deleteRecord.setEnabled(!busy&&!working&&!pending&&!locked&&selectedEntry()!=null);
        retryCleanup.setVisibility(hasPendingCleanup?View.VISIBLE:View.GONE);
        retryCleanup.setEnabled(!busy&&!working&&!pending&&!locked);
        boolean ended=wasBusy&&!busy;wasBusy=busy;
        if(ended)refreshSessions();
        else if(refreshNeeded&&!busy&&!working&&!pending&&!locked)refreshSessions();
    }
    private static int titleFor(Phase phase) {
        switch(phase) {
            case IDLE:return R.string.status_idle;case STARTING:return R.string.starting;
            case RECORDING:return R.string.status_recording;case STOPPING:return R.string.saving;
            case SAVED:return R.string.status_saved;case INTERRUPTED:return R.string.status_interrupted;
            case ERROR:return R.string.status_error;default:return R.string.status_unknown;
        }
    }
    private static int hintFor(Phase phase) {
        switch(phase) {
            case STARTING:return R.string.hint_starting;case RECORDING:return R.string.hint_recording;
            case STOPPING:return R.string.hint_saving;case SAVED:return R.string.hint_saved;
            default:return R.string.hint_idle;
        }
    }
    private String countText(long count){return count<0?"—":numbers.format(count);}
    private static void setText(TextView view,String value){if(!value.contentEquals(view.getText()))view.setText(value);}
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private final Runnable refresh=new Runnable(){@Override public void run(){if(active){update();ui.postDelayed(this,1000);}}};
    @Override public void onResume(){super.onResume();active=true;RecorderService.uiState(true);refreshSessions();ui.post(refresh);}
    @Override public void onStop(){active=false;ui.removeCallbacks(refresh);RecorderService.uiState(false);super.onStop();}
    @Override public void onSaveInstanceState(Bundle saved) {
        saved.putString("selected_record",selectedId);saved.putBoolean("records_visible",recordsVisible);
        if(pendingExport!=null)saved.putString("export_session",pendingExport.getName());super.onSaveInstanceState(saved);
        if(exportOperation!=null)saved.putString("export_operation",exportOperation.id());
    }
    @Override public void onDestroy(){if(isFinishing()&&!exporting)releaseExport();io.shutdown();super.onDestroy();}
}
