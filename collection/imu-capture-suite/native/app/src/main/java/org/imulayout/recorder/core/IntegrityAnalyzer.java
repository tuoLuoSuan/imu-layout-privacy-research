package org.imulayout.recorder.core;
import java.io.File;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;
public final class IntegrityAnalyzer {
    private static final long S=1_000_000_000L;
    private static double quantile(List<Long> values,double p) {
        if(values.isEmpty())return 0;
        ArrayList<Long> sorted=new ArrayList<>(values);Collections.sort(sorted);
        double x=(sorted.size()-1)*p;int i=(int)x;return sorted.get(i)+(sorted.get(Math.min(i+1,sorted.size()-1))-sorted.get(i))*(x-i);
    }
    private static JSONObject intervals(List<Long> values,boolean strict) {
        ArrayList<Long> positive=new ArrayList<>();JSONArray over100=new JSONArray(),over1=new JSONArray();int regression=0,duplicate=0;
        for(int i=0;i<values.size();i++) {
            long v=values.get(i);if(v<0)regression++;if(v==0)duplicate++;if(v>0)positive.add(v);
            JSONObject item=Jsons.object("after_row",i+1,"interval_ns",v);
            if(v>100_000_000L)over100.put(item);if(v>S)over1.put(item);
        }
        return Jsons.object("positive_count",positive.size(),"min_ns",positive.isEmpty()?0:Collections.min(positive),
            "median_ns",quantile(positive,.5),"p95_ns",quantile(positive,.95),"max_ns",positive.isEmpty()?0:Collections.max(positive),
            "regressions",regression,"duplicates",duplicate,"over_100ms",over100,"over_1s",over1,
            "passed",regression==0 && (!strict||duplicate==0) && over1.length()==0);
    }
    private static boolean foreground(JSONArray states,long start,long end) throws Exception {
        String state="unknown";long prior=Long.MIN_VALUE;
        for(int i=0;i<states.length();i++) {
            JSONObject s=states.getJSONObject(i);long t=s.getLong("elapsed_ns");
            if(t<prior)return false;prior=t;
            if(t<=start)state=s.getString("state");
            else if(t<end && !s.getString("state").equals("foreground"))return false;
        }
        return state.equals("foreground");
    }
    private static long count(JSONObject m,String key,int c) {
        JSONArray a=m.optJSONArray(key);return a==null?-1:a.optLong(c,-1);
    }
    public static JSONObject analyze(File dir,JSONObject m) throws Exception {
        long start=m.optLong("collection_start_elapsed_ns",0),end=m.optLong("stop_elapsed_ns",start);
        JSONArray channels=new JSONArray(),warnings=new JSONArray();boolean eventPass=true,deliveryPass=true,storagePass=true,baselinePass=true;
        JSONArray states=m.optJSONArray("states");if(states==null)states=new JSONArray();
        for(int c=0;c<2;c++) {
            List<Long> eventDelta=new ArrayList<>(),deliveryDelta=new ArrayList<>(),queueDelay=new ArrayList<>(),base=new ArrayList<>();
            File f=new File(dir,RecordingContract.CHANNELS[c]+".csv");
            long rows=0,previous=0,previousReceived=0,previousSeq=0,first=0,last=0,baselineFirst=0,baselineLast=0,baselineSamples=0,excluded=0;
            boolean rowValid=true;JSONArray parseErrors=new JSONArray();
            if(f.exists())try(java.io.BufferedReader reader=Files.newBufferedReader(f.toPath(),StandardCharsets.UTF_8)) {
                String header=reader.readLine(),line;
                if(header==null || !header.startsWith("sequence,sensor_timestamp_ns,"))rowValid=false;
                while((line=reader.readLine())!=null) {
                    try {
                        String[] a=line.split(",",-1);if(a.length!=8)throw new IllegalArgumentException("expected 8 fields");
                        long seq=Long.parseLong(a[0]),t=Long.parseLong(a[1]),r=Long.parseLong(a[2]),d=Long.parseLong(a[3]);
                        for(int j=4;j<7;j++)if(!Double.isFinite(Double.parseDouble(a[j])))throw new IllegalArgumentException("non-finite value");
                        if(seq!=previousSeq+1)rowValid=false;
                        if(rows>0){eventDelta.add(t-previous);deliveryDelta.add(r-previousReceived);}
                        if(rows==0)first=t;
                        if(d<r)rowValid=false;queueDelay.add(d-r);
                        if(t>=start && t<start+2*S)excluded++;
                        if(t>=start+2*S && t<start+60*S){
                            if(baselineSamples>0)base.add(t-baselineLast);else baselineFirst=t;
                            baselineLast=t;baselineSamples++;
                        }
                        rows++;previous=t;last=t;previousReceived=r;previousSeq=seq;
                    } catch(Exception e){rowValid=false;parseErrors.put(Jsons.object("line",rows+2,"error",e.toString()));}
                }
            } else rowValid=false;
            JSONObject ev=intervals(eventDelta,true),arr=intervals(deliveryDelta,false),bl=intervals(base,true);
            boolean counts=rows>0 && rowValid && count(m,"received",c)==rows && count(m,"enqueued",c)==rows
                && count(m,"written",c)==rows && count(m,"confirmed",c)==rows && count(m,"dropped",c)==0;
            boolean edges=rows>0 && first>=start && first-start<=S && end>=last && end-last<=S;
            boolean baseline=baselineSamples>0 && bl.getInt("positive_count")>=1000 && bl.getBoolean("passed")
                && baselineFirst-(start+2*S)<=S && start+60*S-baselineLast<=S && end>=start+60*S
                && foreground(states,start+2*S,start+60*S);
            double median=bl.getDouble("median_ns");JSONArray byState=new JSONArray();boolean stable=baseline;
            for(int j=0;j<states.length();j++) {
                JSONObject st=states.getJSONObject(j);long lo=Math.max(start,st.getLong("elapsed_ns"));
                long hi=j+1<states.length()?Math.min(end,states.getJSONObject(j+1).getLong("elapsed_ns")):end;
                List<Long> deltas=new ArrayList<>();long t=first;
                for(long delta:eventDelta){long next=t+delta;if(t>=lo && next<hi && delta>0)deltas.add(delta);t=next;}
                double med=quantile(deltas,.5);boolean enough=deltas.size()>=10;
                boolean ok=baseline && enough && med>=median*.8 && med<=median*1.2;
                if(hi-lo>=S && !ok)stable=false;
                byState.put(Jsons.object("state",st.getString("state"),"start_ns",lo,"end_ns",hi,"interval_count",deltas.size(),"median_ns",med,"status",!enough?"unknown":ok?"pass":"fail"));
            }
            if(states.length()==0)stable=false;
            eventPass &= rows>1 && ev.getBoolean("passed") && edges;
            deliveryPass &= rows>1 && arr.getBoolean("passed");storagePass &= counts;baselinePass &= stable;
            if(ev.getJSONArray("over_100ms").length()+arr.getJSONArray("over_100ms").length()>0)
                warnings.put(Jsons.object("channel",RecordingContract.CHANNELS[c],"type","interval_over_100ms","event_count",ev.getJSONArray("over_100ms").length(),"delivery_count",arr.getJSONArray("over_100ms").length()));
            JSONObject baselineObj=Jsons.object("window_start_ns",start+2*S,"window_end_exclusive_ns",start+60*S,"sample_count",baselineSamples,
                "excluded_startup_samples",excluded,"rule","exclude_first_2s_from_baseline_only","valid",baseline,"median_ns",median,"intervals",bl,"threshold_version","r2",
                "actual_coverage_start_ns",baselineFirst,"actual_coverage_end_ns",baselineLast,"foreground_observation_covers_window",foreground(states,start+2*S,start+60*S));
            channels.put(Jsons.object("name",RecordingContract.CHANNELS[c],"rows",rows,"count_reconciliation",counts,"parse_errors",parseErrors,
                "event_intervals",ev,"delivery_intervals",arr,"queue_delay_ns",intervals(queueDelay,false),"first_event_ns",first,"last_event_ns",last,
                "head_gap_ns",rows==0?JSONObject.NULL:first-start,"tail_gap_ns",rows==0?JSONObject.NULL:end-last,"baseline",baselineObj,"states",byState));
        }
        List<ClockMapping.Anchor> anchors=new ArrayList<>();File anchorFile=new File(dir,"anchors.csv");JSONArray rawAnchors=new JSONArray();
        if(anchorFile.exists())try(java.io.BufferedReader reader=Files.newBufferedReader(anchorFile.toPath(),StandardCharsets.UTF_8)) {
            reader.readLine();String line;while((line=reader.readLine())!=null)try{
                String[] v=line.split(",");ClockMapping.Anchor a=new ClockMapping.Anchor(Long.parseLong(v[1]),Long.parseLong(v[2]),Long.parseLong(v[3]));anchors.add(a);
                rawAnchors.put(Jsons.object("before_ns",a.before,"wall_ms",a.wallMs,"after_ns",a.after,"valid",a.valid(),"reason",a.valid()?"valid":a.after<=a.before?"non_increasing_read":"read_interval_too_wide"));
            }catch(Exception e){anchors.add(new ClockMapping.Anchor(0,0,0));rawAnchors.put(Jsons.object("valid",false,"reason","parse_error"));}
        }
        ClockMapping.Result map=ClockMapping.build(anchors,start,end);JSONArray mapped=new JSONArray(),unmapped=new JSONArray();
        for(ClockMapping.Interval i:map.mapped)mapped.put(Jsons.object("start_ns",i.start,"end_ns",i.end,"reason",i.reason));
        for(ClockMapping.Interval i:map.unmapped)unmapped.put(Jsons.object("start_ns",i.start,"end_ns",i.end,"reason",i.reason));
        boolean complete=m.optString("completion_state").equals("complete") && !m.optBoolean("visibility_condition_failed",false);
        JSONArray tails=new JSONArray();Double stopWall=null;
        for(int i=1;i<anchors.size();i++) {
            ClockMapping.Anchor a=anchors.get(i-1),b=anchors.get(i);long delta=b.midpoint()-a.midpoint();
            if(a.valid() && b.valid() && delta>0 && delta<=15*S && Math.abs((b.wallMs-a.wallMs)-delta/1e6)<=100
                    && a.midpoint()<=end && end<=b.midpoint())stopWall=a.wallMs+(end-a.midpoint())*(b.wallMs-a.wallMs)/(double)delta;
        }
        JSONArray mtimes=m.optJSONArray("source_mtimes");
        if(mtimes!=null)for(int i=0;i<mtimes.length();i++){
            JSONObject t=mtimes.getJSONObject(i);double lag=stopWall==null?0:stopWall-t.getLong("mtime_wall_ms");
            tails.put(Jsons.object("file",t.getString("file"),"lag_ms",stopWall==null?JSONObject.NULL:lag,"status",stopWall==null?"unknown":lag>10000?"warning":"no_lag_warning"));
            if(stopWall!=null && lag>10000)warnings.put(Jsons.object("type","file_tail_update_lag","file",t.getString("file"),"lag_ms",lag,"causal_diagnosis",false));
        }
        JSONArray io=new JSONArray();File eventsFile=new File(dir,"events.jsonl");
        if(eventsFile.exists())try(java.io.BufferedReader reader=Files.newBufferedReader(eventsFile.toPath(),StandardCharsets.UTF_8)){
            String line;while((line=reader.readLine())!=null)try{JSONObject e=new JSONObject(line);if(e.optString("type").equals("csv_io"))io.put(e.getJSONObject("details"));}catch(Exception ignored){}
        }
        return Jsons.object("format_version",1,"criteria_version","r2","completion",complete?"pass":"fail",
            "event_continuity",eventPass?"pass":"fail","delivery_continuity",deliveryPass?"pass":"fail","storage_integrity",storagePass?"pass":"fail",
            "baseline_stability",baselinePass?"pass":"unknown_or_fail","utc_mapping",mapped.length()==0?"unavailable":unmapped.length()==0?"complete":"partial",
            "external_observation","requires_independent_review","data_checks_passed",complete&&eventPass&&deliveryPass&&storagePass&&baselinePass,
            "overall","pending_external_review","warnings",warnings,"channels",channels,"anchors",rawAnchors,"valid_mapping_intervals",mapped,"unmapped_intervals",unmapped,
            "csv_io",io,"wake_lock_operations",m.optJSONArray("wake_lock_operations"),"file_tail_update_lag",tails);
    }
}
