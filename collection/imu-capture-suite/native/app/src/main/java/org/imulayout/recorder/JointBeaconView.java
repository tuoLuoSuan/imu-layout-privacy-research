package org.imulayout.recorder;
import android.content.Context;
import android.graphics.*;
import android.view.View;
/** Render requests are logged; physical display latency is deliberately unknown. */
public final class JointBeaconView extends View {
 private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
 private long last=-1;
 public JointBeaconView(Context c){super(c);setContentDescription("联机检查画面序号");}
 @Override protected void onDraw(Canvas canvas){
  super.onDraw(canvas);long before=AndroidRecordingRuntime.now(),start=RecorderService.collectionStartNs();
  long code=start>0?Math.max(0,(before-start)/1000000000L):-1;
  canvas.drawColor(code>=0&&code%2==0?Color.rgb(19,61,65):Color.rgb(239,244,246));
  paint.setColor(code>=0&&code%2==0?Color.WHITE:Color.rgb(20,40,50));paint.setTextAlign(Paint.Align.CENTER);
  paint.setTextSize(15*getResources().getDisplayMetrics().scaledDensity);canvas.drawText("电脑录像拍到这里即可",getWidth()/2f,25*getResources().getDisplayMetrics().density,paint);
  paint.setTextSize(49*getResources().getDisplayMetrics().scaledDensity);canvas.drawText(code<0?"等待开始":String.format(java.util.Locale.ROOT,"%03d",code),getWidth()/2f,82*getResources().getDisplayMetrics().density,paint);
  long after=AndroidRecordingRuntime.now();if(code>=0&&code!=last){last=code;RecorderService.recordBeacon(code,before,after);}
  if(isAttachedToWindow())postInvalidateDelayed(100);
 }
}
