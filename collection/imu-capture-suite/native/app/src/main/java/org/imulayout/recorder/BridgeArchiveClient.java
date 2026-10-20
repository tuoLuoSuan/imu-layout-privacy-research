package org.imulayout.recorder;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.zip.CRC32;
import org.json.JSONObject;

/** One bounded, same-session localhost snapshot. No retry and no external network. */
public final class BridgeArchiveClient {
 private BridgeArchiveClient(){}
 public static byte[] fetch(String sid)throws Exception{return fetch(sid,38741);}
 static byte[] fetch(String sid,int port)throws Exception{
  if(!sid.matches("[A-Za-z0-9_-]{1,64}"))throw new IOException("记录身份无效");
  String nonce=UUID.randomUUID().toString();HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:"+port+"/export").openConnection();
  try{
   // Export must not leave an old bridge-generation socket available to the next recording.
   c.setRequestMethod("POST");c.setInstanceFollowRedirects(false);c.setConnectTimeout(2500);c.setReadTimeout(8000);c.setDoOutput(true);c.setUseCaches(false);c.setRequestProperty("Content-Type","application/json; charset=utf-8");c.setRequestProperty("Connection","close");
   byte[] body=new JSONObject().put("kind","export_session").put("sid",sid).put("nonce",nonce).toString().getBytes(StandardCharsets.UTF_8);c.setFixedLengthStreamingMode(body.length);
   try(OutputStream o=c.getOutputStream()){o.write(body);}
   int code=c.getResponseCode();if(code!=200)throw new IOException("连接插件未能导出本条日志（"+code+"）");
   if(!sid.equals(c.getHeaderField("X-IMU-Session"))||!nonce.equals(c.getHeaderField("X-IMU-Nonce")))throw new IOException("连接插件的记录身份不一致");
   ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream in=c.getInputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(bytes.size()+n>4_194_304)throw new IOException("手表日志超出导出上限");bytes.write(b,0,n);}}
   byte[] raw=bytes.toByteArray();CRC32 crc=new CRC32();crc.update(raw);if(!String.format(java.util.Locale.ROOT,"%08x",crc.getValue()).equals(c.getHeaderField("X-IMU-CRC32")))throw new IOException("手表日志传输校验不一致");
   JointBundleExporter.validateJournal(raw,sid);return raw;
  }finally{c.disconnect();}
 }
}
