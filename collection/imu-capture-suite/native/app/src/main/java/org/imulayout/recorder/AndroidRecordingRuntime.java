package org.imulayout.recorder;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.hardware.*;
import android.os.*;
import org.json.*;
import org.imulayout.recorder.core.Jsons;

public final class AndroidRecordingRuntime {
    public static final String CHANNEL="imu_recording";
    public static final int NOTIFICATION_ID=1001;
    public final SensorManager sensors;
    public final PowerManager.WakeLock wakeLock;
    private final Context context;
    public AndroidRecordingRuntime(Context c) {
        context=c;sensors=c.getSystemService(SensorManager.class);
        wakeLock=c.getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"imu-recorder:session");
        wakeLock.setReferenceCounted(false);
    }
    public static long now(){return SystemClock.elapsedRealtimeNanos();}
    public static void createChannel(Context c) {
        c.getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel(CHANNEL,"IMU 采集状态",NotificationManager.IMPORTANCE_LOW));
    }
    public static boolean notificationAllowed(Context c) {
        NotificationManager n=c.getSystemService(NotificationManager.class);NotificationChannel ch=n.getNotificationChannel(CHANNEL);
        return c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED
            && n.areNotificationsEnabled() && ch!=null && ch.getImportance()!=NotificationManager.IMPORTANCE_NONE;
    }
    public static Notification notification(Context c,String text) {
        PendingIntent open=PendingIntent.getActivity(c,0,new Intent(c,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(c,1,new Intent(c,RecorderService.class).setAction("stop"),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(c,CHANNEL).setSmallIcon(android.R.drawable.ic_menu_compass).setContentTitle("IMU 正在采集")
            .setContentText(text).setOngoing(true).setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE)
            .setContentIntent(open).addAction(new Notification.Action.Builder(android.R.drawable.ic_media_pause,"停止",stop).build()).build();
    }
    public JSONObject notificationObservation() {
        try {
            boolean found=false;
            for(android.service.notification.StatusBarNotification n:context.getSystemService(NotificationManager.class).getActiveNotifications())
                if(n.getId()==NOTIFICATION_ID)found=true;
            return Jsons.object("allowed",notificationAllowed(context),"own_notification_present",found,"visibility_proven",false);
        } catch(Exception e){return Jsons.object("own_notification_present","unknown","error",e.toString());}
    }
    public JSONObject powerObservation() {
        Intent b=context.registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        return Jsons.object("interactive",context.getSystemService(PowerManager.class).isInteractive(),
            "keyguard_locked",context.getSystemService(KeyguardManager.class).isKeyguardLocked(),
            "plugged",b==null?"unknown":b.getIntExtra(BatteryManager.EXTRA_PLUGGED,-1),"wake_lock_is_held",wakeLock.isHeld());
    }
    public static JSONObject sensorInfo(Sensor s) {
        return Jsons.object("name",s.getName(),"vendor",s.getVendor(),"version",s.getVersion(),"type",s.getType(),
            "min_delay_us",s.getMinDelay(),"max_delay_us",s.getMaxDelay(),"range",s.getMaximumRange(),"resolution",s.getResolution(),
            "power_ma",s.getPower(),"wake_up",s.isWakeUpSensor(),"fifo_reserved",s.getFifoReservedEventCount(),"fifo_max",s.getFifoMaxEventCount(),"reporting_mode",s.getReportingMode());
    }
}
