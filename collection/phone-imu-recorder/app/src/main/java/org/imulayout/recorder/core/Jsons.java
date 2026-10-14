package org.imulayout.recorder.core;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;

public final class Jsons {
    private Jsons() {}
    public static JSONObject object(Object... pairs) {
        JSONObject o=new JSONObject();
        try {for(int i=0;i<pairs.length;i+=2)o.put(pairs[i].toString(),pairs[i+1]==null?JSONObject.NULL:pairs[i+1]);}
        catch(JSONException e){throw new IllegalArgumentException(e);}return o;
    }
    public static JSONArray longs(long[] values) {JSONArray a=new JSONArray();for(long v:values)a.put(v);return a;}
    public static JSONObject read(File f) throws Exception {return new JSONObject(new String(Files.readAllBytes(f.toPath()),StandardCharsets.UTF_8));}
    public static void save(File f,JSONObject o) throws Exception {
        File temp=new File(f.getParentFile(),f.getName()+".partial");
        try(FileOutputStream out=new FileOutputStream(temp)) {
            out.write((o.toString(2)+"\n").getBytes(StandardCharsets.UTF_8));out.flush();out.getFD().sync();
        }
        try {Files.move(temp.toPath(),f.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
        catch(AtomicMoveNotSupportedException e){Files.move(temp.toPath(),f.toPath(),StandardCopyOption.REPLACE_EXISTING);}
    }
    public static String sha256(File f) throws Exception {
        MessageDigest d=MessageDigest.getInstance("SHA-256");
        try(InputStream in=new FileInputStream(f)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)d.update(b,0,n);}
        StringBuilder s=new StringBuilder();for(byte b:d.digest())s.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return s.toString();
    }
}
