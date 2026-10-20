package org.imulayout.recorder;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;
import org.imulayout.recorder.ui.CompletionMessage;
import org.imulayout.recorder.ui.RecorderPresentation;
public class ClockBridgeClientTest {
 interface Reply{JSONObject get(JSONObject request)throws Exception;}
 static final class LocalServer implements AutoCloseable{
  final ServerSocket server;final AtomicInteger requests=new AtomicInteger();final AtomicReference<String> connectionHeader=new AtomicReference<>();final Thread thread;volatile Throwable error;
  LocalServer(int status,Reply reply)throws Exception{
   server=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"));
   thread=new Thread(()->{try{while(!server.isClosed()){try(Socket socket=server.accept()){
    BufferedInputStream in=new BufferedInputStream(socket.getInputStream());String first=line(in);assertTrue(first.startsWith("POST /bridge "));String h;int length=0;
    while(!(h=line(in)).isEmpty()){if(h.toLowerCase(java.util.Locale.ROOT).startsWith("content-length:"))length=Integer.parseInt(h.substring(h.indexOf(':')+1).trim());if(h.toLowerCase(java.util.Locale.ROOT).startsWith("connection:"))connectionHeader.set(h.substring(h.indexOf(':')+1).trim());}
    JSONObject req=new JSONObject(new String(in.readNBytes(length),StandardCharsets.UTF_8));requests.incrementAndGet();byte[] body=reply.get(req).toString().getBytes(StandardCharsets.UTF_8);
    OutputStream out=socket.getOutputStream();out.write(("HTTP/1.1 "+status+" Result\r\nContent-Type: application/json\r\nContent-Length: "+body.length+"\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.write(body);out.flush();
   }}}catch(Throwable e){if(!server.isClosed())error=e;}},"synthetic-loopback-server");thread.setDaemon(true);thread.start();
  }
  static String line(InputStream in)throws Exception{ByteArrayOutputStream b=new ByteArrayOutputStream();int c;while((c=in.read())!=-1){if(c=='\n')break;if(c!='\r')b.write(c);if(b.size()>16384)throw new IOException("header too large");}if(c==-1&&b.size()==0)throw new EOFException();return b.toString(StandardCharsets.US_ASCII);}
  int port(){return server.getLocalPort();}
  public void close()throws Exception{server.close();thread.join(2000);if(error!=null)throw new AssertionError(error);}
 }
 @Test public void actualLocalHttpEchoAndNativeEvents()throws Exception{
  try(LocalServer server=new LocalServer(200,req->new JSONObject().put("kind","native_clock_reply").put("sid",req.getString("sid")).put("seq",req.getInt("seq")).put("nonce",req.getString("nonce")).put("n1_ns",req.getLong("n1_ns")).put("p2_us",1792300000000000L).put("p3_us",1792300000000100L).put("watch_sid","watch-session").put("watch_rows",12).put("watch_clock_observations",2).put("watch_finished",true).put("watch_stop_reason","duration").put("physical_clock_accepted",false))){
   CountDownLatch done=new CountDownLatch(1);AtomicInteger events=new AtomicInteger(),failures=new AtomicInteger();AtomicLong clock=new AtomicLong(10000000000L);
   ClockBridgeClient client=new ClockBridgeClient("native-session",v->{assertEquals("joint_native_exchange",v.optString("type"));events.incrementAndGet();},done::countDown,e->failures.incrementAndGet(),()->clock.getAndAdd(10000000L),server.port());
   try{client.start();assertTrue(done.await(4,TimeUnit.SECONDS));assertEquals(1,events.get());assertEquals(1,client.count());assertEquals(0,failures.get());assertEquals(1,server.requests.get());assertTrue(client.closeAndJoin(2000));}finally{client.closeAndJoin(2000);}
  }
 }
 @Test public void pollingExplicitlyClosesTcpConnectionBeforeNextBridgeGeneration()throws Exception{
  try(LocalServer server=new LocalServer(409,req->new JSONObject().put("error","not prepared"))){
   CountDownLatch failed=new CountDownLatch(1);
   ClockBridgeClient client=new ClockBridgeClient("next-native-session",v->{},()->fail("unexpected success"),e->failed.countDown(),System::nanoTime,server.port());
   try{
    client.start();assertTrue(failed.await(4,TimeUnit.SECONDS));assertTrue(client.closeAndJoin(2000));
    assertEquals("close",server.connectionHeader.get());
    assertEquals(1,server.requests.get());assertEquals(0,client.count());
   }finally{client.closeAndJoin(2000);}
  }
 }
 @Test public void successThenFailureThenSuccessUseIndependentSessionsInOneProcess()throws Exception{
  try(LocalServer server=new LocalServer(200,req->new JSONObject().put("kind","native_clock_reply").put("sid",req.getString("sid")).put("seq",req.getInt("seq")).put("nonce",req.getString("nonce")).put("n1_ns",req.getLong("n1_ns")).put("p2_us",1792300000000000L).put("p3_us",1792300000000100L).put("watch_sid","watch-"+req.getString("sid")).put("watch_rows",12).put("watch_clock_observations",2).put("watch_finished",true).put("watch_failed",req.getString("sid").equals("failed-session")).put("watch_failure_stage","block").put("watch_stop_reason",req.getString("sid").equals("failed-session")?"failure":"duration").put("physical_clock_accepted",false))){
   for(String sid:new String[]{"first-session","failed-session","next-session"}){
    CountDownLatch ended=new CountDownLatch(1);AtomicInteger successes=new AtomicInteger(),failures=new AtomicInteger();AtomicLong clock=new AtomicLong(10000000000L);
    ClockBridgeClient client=new ClockBridgeClient(sid,v->{if(v.optString("type").equals("joint_native_exchange"))assertEquals(sid,v.optJSONObject("details").optJSONObject("request").optString("sid"));},()->{successes.incrementAndGet();ended.countDown();},e->{failures.incrementAndGet();ended.countDown();},()->clock.getAndAdd(10000000L),server.port());
    try{client.start();assertTrue(ended.await(4,TimeUnit.SECONDS));assertTrue(client.closeAndJoin(2000));assertEquals(1,client.count());assertEquals(sid.equals("failed-session")?0:1,successes.get());assertEquals(sid.equals("failed-session")?1:0,failures.get());assertEquals("close",server.connectionHeader.get());}finally{client.closeAndJoin(2000);}
   }
   assertEquals(3,server.requests.get());
  }
 }
 @Test public void localFailurePreservesOneFailureWithoutRetry()throws Exception{
  try(LocalServer server=new LocalServer(409,req->new JSONObject().put("error","synthetic refusal"))){
   CountDownLatch failed=new CountDownLatch(1);AtomicInteger failureEvents=new AtomicInteger();ClockBridgeClient client=new ClockBridgeClient("native-session",v->{if(v.optString("type").equals("joint_native_failure"))failureEvents.incrementAndGet();},()->fail("unexpected success"),e->failed.countDown(),System::nanoTime,server.port());
   try{client.start();assertTrue(failed.await(4,TimeUnit.SECONDS));assertTrue(client.closeAndJoin(2000));assertEquals(1,failureEvents.get());assertEquals(1,server.requests.get());assertEquals(0,client.count());}finally{client.closeAndJoin(2000);}
  }
 }
 @Test public void actualHttpRefusalRemainsVisibleInFinalPresentation()throws Exception{
  try(LocalServer server=new LocalServer(409,req->new JSONObject().put("error","synthetic session mismatch"))){
   CountDownLatch failed=new CountDownLatch(1);AtomicReference<String> cause=new AtomicReference<>();
   ClockBridgeClient client=new ClockBridgeClient("native-session",v->{},()->fail("unexpected success"),e->{cause.set(e);failed.countDown();},System::nanoTime,server.port());
   try{
    client.start();assertTrue(failed.await(4,TimeUnit.SECONDS));assertTrue(client.closeAndJoin(2000));
    String message=CompletionMessage.format(true,"joint_bridge_failed",cause.get(),client.status());
    assertTrue(message.contains("409"));assertTrue(message.contains("synthetic session mismatch"));
    assertEquals(RecorderPresentation.Phase.INTERRUPTED,RecorderPresentation.from(message,false,false).phase);
    assertEquals(1,server.requests.get());assertEquals(0,client.count());
   }finally{client.closeAndJoin(2000);}
  }
 }
 @Test public void actualLocalHttpWatchFailureStopsWithoutSuccessOrPollingAgain()throws Exception{
  try(LocalServer server=new LocalServer(200,req->new JSONObject().put("kind","native_clock_reply").put("sid",req.getString("sid")).put("seq",req.getInt("seq")).put("nonce",req.getString("nonce")).put("n1_ns",req.getLong("n1_ns")).put("p2_us",1792300000000000L).put("p3_us",1792300000000100L).put("watch_sid","watch-session").put("watch_rows",0).put("watch_clock_observations",0).put("watch_finished",true).put("watch_failed",true).put("watch_failure_stage","block").put("watch_stop_reason","failure").put("physical_clock_accepted",false))){
   CountDownLatch failed=new CountDownLatch(1);AtomicInteger success=new AtomicInteger(),failureEvents=new AtomicInteger();AtomicLong clock=new AtomicLong(10000000000L);
   ClockBridgeClient client=new ClockBridgeClient("native-session",v->{if(v.optString("type").equals("joint_watch_failure"))failureEvents.incrementAndGet();},success::incrementAndGet,e->failed.countDown(),()->clock.getAndAdd(10000000L),server.port());
   try{client.start();assertTrue(failed.await(4,TimeUnit.SECONDS));assertTrue(client.closeAndJoin(2000));assertEquals(0,success.get());assertEquals(1,failureEvents.get());assertEquals(1,server.requests.get());assertTrue(client.status().contains("block"));}finally{client.closeAndJoin(2000);}
  }
 }
}
