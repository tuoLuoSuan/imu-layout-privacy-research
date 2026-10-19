package org.imulayout.recorder.core;
import org.imulayout.recorder.SessionExporter;
import org.imulayout.recorder.JointBundleExporter;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.zip.*;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;
public class JointBundleExporterTest {
 private File session()throws Exception{File d=Files.createTempDirectory("imu-suite-synthetic-").toFile();Files.writeString(new File(d,"raw.txt").toPath(),"unchanged source");SessionExporter.seal(d,Jsons.object("session_id","native-session","completion_state","aborted"));return d;}
 private Map<String,byte[]> unzip(byte[] data)throws Exception{Map<String,byte[]> r=new HashMap<>();try(ZipInputStream z=new ZipInputStream(new ByteArrayInputStream(data))){ZipEntry e;while((e=z.getNextEntry())!=null)r.put(e.getName(),z.readAllBytes());}return r;}
 @Test public void oneBundleRetainsOriginalPhoneZipAndExactWatchLog()throws Exception{File d=session();String before=Jsons.sha256(new File(d,"manifest.json"));byte[] watch="{\"kind\":\"header\",\"format\":\"imu_joint_bridge_v1\",\"native_sid\":\"native-session\"}\n".getBytes(StandardCharsets.UTF_8);ByteArrayOutputStream out=new ByteArrayOutputStream();JointBundleExporter.write(d,watch,"",out);Map<String,byte[]> v=unzip(out.toByteArray());assertEquals(Set.of("phone.zip","watch.jsonl","bundle-manifest.json"),v.keySet());assertArrayEquals(watch,v.get("watch.jsonl"));assertEquals(before,Jsons.sha256(new File(d,"manifest.json")));Map<String,byte[]> phone=unzip(v.get("phone.zip"));assertArrayEquals(Files.readAllBytes(new File(d,"manifest.json").toPath()),phone.get("manifest.json"));JSONObject m=new JSONObject(new String(v.get("bundle-manifest.json"),StandardCharsets.UTF_8));assertTrue(m.getBoolean("watch_included"));assertFalse(m.getBoolean("physical_clock_accepted"));}
 @Test public void missingPluginProducesExplicitPartialBundle()throws Exception{ByteArrayOutputStream out=new ByteArrayOutputStream();JointBundleExporter.write(session(),null,"本机连接不可用",out);Map<String,byte[]> v=unzip(out.toByteArray());assertFalse(v.containsKey("watch.jsonl"));JSONObject m=new JSONObject(new String(v.get("bundle-manifest.json"),StandardCharsets.UTF_8));assertFalse(m.getBoolean("watch_included"));assertTrue(m.getString("watch_export_error").contains("本机连接不可用"));}
 @Test public void foreignWatchJournalIsNeverMerged()throws Exception{byte[] bad="{\"kind\":\"header\",\"format\":\"imu_joint_bridge_v1\",\"native_sid\":\"foreign\"}\n".getBytes(StandardCharsets.UTF_8);assertThrows(IOException.class,()->JointBundleExporter.write(session(),bad,"",new ByteArrayOutputStream()));}
}
