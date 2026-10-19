package org.imulayout.recorder;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.zip.*;
import org.json.*;
import org.imulayout.recorder.core.Jsons;

/** Outer archive only: existing sealed session members and manifest are never changed. */
public final class JointBundleExporter {
 private JointBundleExporter(){}
 public static void validateJournal(byte[] raw,String sid)throws IOException{
  try{
   if(raw==null||raw.length==0||raw.length>4_194_304)throw new IOException("手表日志长度异常");
   String first=new String(raw,StandardCharsets.UTF_8).split("\n",2)[0];JSONObject h=new JSONObject(first);
   if(!"header".equals(h.optString("kind"))||!"imu_joint_bridge_v1".equals(h.optString("format"))||!sid.equals(h.optString("native_sid")))throw new IOException("手表日志与这条手机记录不匹配");
  }catch(IOException e){throw e;}catch(Exception e){throw new IOException("手表日志头无法读取",e);}
 }
 private static String sha(byte[] raw)throws Exception{byte[] d=MessageDigest.getInstance("SHA-256").digest(raw);StringBuilder s=new StringBuilder();for(byte b:d)s.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return s.toString();}
 private static void part(ZipOutputStream out,JSONArray entries,String name,byte[] raw)throws Exception{out.putNextEntry(new ZipEntry(name));out.write(raw);out.closeEntry();entries.put(Jsons.object("path",name,"bytes",raw.length,"sha256",sha(raw)));}
 public static void write(File session,byte[] watch,String warning,OutputStream target)throws Exception{
  String sid=Jsons.read(new File(session,"metadata.json")).getString("session_id");
  if(watch!=null)validateJournal(watch,sid);
  ByteArrayOutputStream nativeBytes=new ByteArrayOutputStream();SessionExporter.zip(session,nativeBytes);
  JSONArray files=new JSONArray();
  try(ZipOutputStream out=new ZipOutputStream(target)){
   part(out,files,"phone.zip",nativeBytes.toByteArray());
   if(watch!=null)part(out,files,"watch.jsonl",watch);
   JSONObject manifest=Jsons.object("kind","imu_capture_bundle_v1","schema_version",1,"native_sid",sid,"watch_included",watch!=null,"watch_export_error",warning==null?"":warning,"physical_clock_accepted",false,"research_validated",false,"files",files);
   out.putNextEntry(new ZipEntry("bundle-manifest.json"));out.write((manifest.toString(2)+"\n").getBytes(StandardCharsets.UTF_8));out.closeEntry();
  }
 }
}
