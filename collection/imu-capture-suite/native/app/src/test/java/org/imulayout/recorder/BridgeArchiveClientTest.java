package org.imulayout.recorder;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import java.util.zip.CRC32;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;
public class BridgeArchiveClientTest {
 static final byte[] RAW="{\"kind\":\"header\",\"format\":\"imu_joint_bridge_v1\",\"native_sid\":\"native-session\"}\n".getBytes(StandardCharsets.UTF_8);
 static class Server implements AutoCloseable{
  final ServerSocket socket;final Thread worker;final AtomicInteger requests=new AtomicInteger();final AtomicReference<String> connectionHeader=new AtomicReference<>();volatile Throwable error;
  Server(boolean badCrc,boolean badIdentity)throws Exception{socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"));worker=new Thread(()->{try(Socket s=socket.accept()){
   InputStream in=new BufferedInputStream(s.getInputStream());assertTrue(ClockBridgeClientTest.LocalServer.line(in).startsWith("POST /export "));String line;int length=0;while(!(line=ClockBridgeClientTest.LocalServer.line(in)).isEmpty()){if(line.toLowerCase(java.util.Locale.ROOT).startsWith("content-length:"))length=Integer.parseInt(line.substring(line.indexOf(':')+1).trim());if(line.toLowerCase(java.util.Locale.ROOT).startsWith("connection:"))connectionHeader.set(line.substring(line.indexOf(':')+1).trim());}
   JSONObject req=new JSONObject(new String(in.readNBytes(length),StandardCharsets.UTF_8));requests.incrementAndGet();CRC32 crc=new CRC32();crc.update(RAW);
   String head="HTTP/1.1 200 OK\r\nContent-Length: "+RAW.length+"\r\nX-IMU-Session: "+(badIdentity?"foreign":req.getString("sid"))+"\r\nX-IMU-Nonce: "+req.getString("nonce")+"\r\nX-IMU-CRC32: "+(badCrc?"00000000":String.format(java.util.Locale.ROOT,"%08x",crc.getValue()))+"\r\nConnection: close\r\n\r\n";
   s.getOutputStream().write(head.getBytes(StandardCharsets.US_ASCII));s.getOutputStream().write(RAW);s.getOutputStream().flush();
  }catch(Throwable e){if(!socket.isClosed())error=e;}});worker.setDaemon(true);worker.start();}
  public void close()throws Exception{socket.close();worker.join(2000);if(error!=null)throw new AssertionError(error);}
 }
 @Test public void actualLocalArchiveBytesArePreserved()throws Exception{try(Server s=new Server(false,false)){assertArrayEquals(RAW,BridgeArchiveClient.fetch("native-session",s.socket.getLocalPort()));assertEquals(1,s.requests.get());}}
 @Test public void exportExplicitlyClosesTcpConnectionBeforeNextBridgeGeneration()throws Exception{try(Server s=new Server(false,false)){assertArrayEquals(RAW,BridgeArchiveClient.fetch("native-session",s.socket.getLocalPort()));assertEquals("close",s.connectionHeader.get());assertEquals(1,s.requests.get());}}
 @Test public void crcMismatchIsRejectedWithoutRetry()throws Exception{try(Server s=new Server(true,false)){assertThrows(IOException.class,()->BridgeArchiveClient.fetch("native-session",s.socket.getLocalPort()));assertEquals(1,s.requests.get());}}
 @Test public void foreignIdentityIsRejectedWithoutRetry()throws Exception{try(Server s=new Server(false,true)){assertThrows(IOException.class,()->BridgeArchiveClient.fetch("native-session",s.socket.getLocalPort()));assertEquals(1,s.requests.get());}}
}
