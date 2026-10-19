package org.imulayout.recorder;
import android.os.SystemClock;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.function.Consumer;
import java.util.function.LongSupplier;
import org.json.*;
import org.imulayout.recorder.core.ClockBridgeRules;
import org.imulayout.recorder.core.Jsons;
/** Native monotonic ↔ plugin bridge. HTTP never leaves this phone. */
public final class ClockBridgeClient {
 private final String sid;
 private final Consumer<JSONObject> log;
 private final Runnable finished;
 private final Consumer<String> failed;
 private final LongSupplier clock;
 private final int port;
 private final Object gate=new Object();
 private volatile boolean cancelled;
 private volatile HttpURLConnection active;
 private Thread worker;
 private volatile int count;
 private volatile String status="等待本机连接";
 public ClockBridgeClient(String id,Consumer<JSONObject> output,Runnable done,Consumer<String> failure){this(id,output,done,failure,SystemClock::elapsedRealtimeNanos,38741);}
 ClockBridgeClient(String id,Consumer<JSONObject> output,Runnable done,Consumer<String> failure,LongSupplier time,int localPort){if(localPort<1||localPort>65535)throw new IllegalArgumentException("invalid loopback port");sid=id;log=output;finished=done;failed=failure;clock=time;port=localPort;}
 public String status(){return status;}
 public int count(){return count;}
 private void emit(String type,JSONObject details){synchronized(gate){if(!cancelled)log.accept(Jsons.object("type",type,"details",details));}}
 public void start(){worker=new Thread(this::loop,"imu-joint-clock");worker.start();}
 private void loop(){
  for(int seq=0;seq<1800&&!cancelled;seq++){
   try{
    String nonce=UUID.randomUUID().toString();JSONObject req=Jsons.object("kind","native_clock_req","sid",sid,"seq",seq,"nonce",nonce);
    HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:"+port+"/bridge").openConnection();active=c;
    c.setRequestMethod("POST");c.setInstanceFollowRedirects(false);c.setConnectTimeout(2500);c.setReadTimeout(5000);c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json; charset=utf-8");c.setUseCaches(false);
    long n1=clock.getAsLong();req.put("n1_ns",n1);byte[] body=req.toString().getBytes(StandardCharsets.UTF_8);c.setFixedLengthStreamingMode(body.length);
    try(OutputStream out=c.getOutputStream()){out.write(body);}
    int code=c.getResponseCode();ByteArrayOutputStream bytes=new ByteArrayOutputStream();
    try(InputStream in=code==200?c.getInputStream():c.getErrorStream()){
     if(in==null)throw new IOException("本机服务没有回复");byte[] buffer=new byte[2048];int read;
     while((read=in.read(buffer))!=-1){bytes.write(buffer,0,read);if(bytes.size()>16384)throw new IOException("回复超出检查上限");}
    }
    long n4=clock.getAsLong();String raw=bytes.toString(StandardCharsets.UTF_8);
    c.disconnect();active=null;if(cancelled)return;
    if(code!=200)throw new IOException("本机时间桥未接受："+code+" "+raw);
    JSONObject rep=new JSONObject(raw);ClockBridgeRules.checkReply(rep,sid,seq,nonce,n1);
    long[] interval=ClockBridgeRules.bounds(n1,n4,ClockBridgeRules.integer(rep,"p2_us"),ClockBridgeRules.integer(rep,"p3_us"));
    emit("joint_native_exchange",Jsons.object("request",req,"reply",rep,"n1_ns",n1,"n4_ns",n4,"native_minus_plugin_ns_low",interval[0],"native_minus_plugin_ns_high",interval[1],"physical_clock_accepted",false));
    count++;status=rep.optString("watch_sid","").isEmpty()?"手机已连接，请在表上开始":"已连接 · 腕部 "+rep.optLong("watch_rows")+" 条";
    if(rep.getBoolean("watch_finished")){status="本次联机记录已接收，正在保存";if(!cancelled)finished.run();return;}
    Thread.sleep(1000);
   }catch(InterruptedException e){Thread.currentThread().interrupt();return;}
   catch(Exception e){if(cancelled)return;status="连接停止："+e.getMessage();emit("joint_native_failure",Jsons.object("message",e.toString(),"completed_exchanges",count,"partial_preserved",true));if(!cancelled)failed.accept(status);return;}
   finally{HttpURLConnection c=active;active=null;if(c!=null)c.disconnect();}
  }
 }
 public boolean closeAndJoin(long timeoutMs){synchronized(gate){cancelled=true;}HttpURLConnection c=active;if(c!=null)c.disconnect();if(worker!=null){worker.interrupt();try{worker.join(timeoutMs);}catch(InterruptedException e){Thread.currentThread().interrupt();}return !worker.isAlive();}return true;}
}
