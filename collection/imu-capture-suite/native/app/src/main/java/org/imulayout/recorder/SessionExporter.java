package org.imulayout.recorder;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.Comparator;
import java.util.zip.*;
import org.json.*;
import org.imulayout.recorder.core.*;
public final class SessionExporter {
    public static void seal(File dir,JSONObject metadata) throws Exception {
        if(new File(dir,"manifest.json").exists())return;
        Jsons.save(new File(dir,"metadata.json"),metadata);
        Jsons.save(new File(dir,"integrity_report.json"),IntegrityAnalyzer.analyze(dir,metadata));
        Jsons.save(new File(dir,"state.json"),Jsons.object("state","sealed","completion_state",metadata.optString("completion_state","aborted")));
        File[] all=dir.listFiles(f->f.isFile() && !f.getName().equals("manifest.json"));
        if(all==null)throw new IOException("cannot list session files");
        Arrays.sort(all,Comparator.comparing(File::getName));JSONArray entries=new JSONArray();
        for(File f:all) {
            JSONObject entry=Jsons.object("path",f.getName(),"bytes",f.length(),"sha256",Jsons.sha256(f));
            if(f.getName().endsWith(".csv")){
                long lines;try(java.util.stream.Stream<String> stream=Files.lines(f.toPath(),StandardCharsets.UTF_8)){lines=stream.count();}
                entry.put("rows",Math.max(0,lines-1));
            }
            entries.put(entry);
        }
        Jsons.save(new File(dir,"manifest.json"),Jsons.object("format_version",1,"files",entries));
    }
    public static void zip(File dir,OutputStream output) throws Exception {
        File manifest=new File(dir,"manifest.json");if(!manifest.isFile())throw new IOException("session not sealed");
        JSONArray files=Jsons.read(manifest).getJSONArray("files");
        for(int i=0;i<files.length();i++) {
            JSONObject entry=files.getJSONObject(i);String name=entry.getString("path");
            if(name.contains("/") || name.contains("\\") || name.equals(".") || name.equals(".."))throw new IOException("invalid manifest path");
            File f=new File(dir,name);
            if(!f.isFile() || f.length()!=entry.getLong("bytes") || !Jsons.sha256(f).equals(entry.getString("sha256")))throw new IOException("source checksum mismatch: "+name);
        }
        try(ZipOutputStream zip=new ZipOutputStream(output)) {
            for(int i=0;i<=files.length();i++) {
                File f=i==files.length()?manifest:new File(dir,files.getJSONObject(i).getString("path"));
                ZipEntry e=new ZipEntry(f.getName());e.setTime(f.lastModified());zip.putNextEntry(e);
                try(InputStream in=new FileInputStream(f)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)zip.write(b,0,n);}
                zip.closeEntry();
            }
        }
    }
    public static void recover(File root) throws Exception {
        File[] dirs=root.listFiles(f->f.isDirectory()&&!Files.isSymbolicLink(f.toPath()));if(dirs==null)return;
        for(File dir:dirs)if(!new File(dir,"manifest.json").exists()) {
            JSONObject m;
            try{m=Jsons.read(new File(dir,"metadata.json"));}catch(Exception e){m=Jsons.object("format_version",1,"session_id",dir.getName());}
            m.put("completion_state","aborted");m.put("stopped_reason","process_end_unknown");
            m.put("recovered_at_wall_ms",System.currentTimeMillis());m.put("original_stop_elapsed_ns_known",false);
            long last=m.optLong("collection_start_elapsed_ns",0);
            for(String c:RecordingContract.CHANNELS){File f=new File(dir,c+".csv");if(f.exists())try(BufferedReader r=Files.newBufferedReader(f.toPath(),StandardCharsets.UTF_8)){
                String line;while((line=r.readLine())!=null)try{last=Math.max(last,Long.parseLong(line.split(",")[1]));}catch(Exception ignored){}
            }}
            m.put("stop_elapsed_ns",last);m.put("stop_elapsed_ns_source","last_raw_event_lower_bound_only");
            Jsons.save(new File(dir,"recovery.json"),Jsons.object("raw_files_modified",false,"reason","incomplete_session_after_process_end","missing_tail_not_reconstructed",true));
            seal(dir,m);
        }
    }
}
