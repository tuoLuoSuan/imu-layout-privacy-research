package org.imulayout.recorder.core;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import org.json.JSONObject;
import java.util.function.LongSupplier;
import java.util.function.Consumer;
public final class SessionFiles {
    public Thread worker;
    public volatile boolean finished;
    public volatile String error;
    public final long[] written={0,0},confirmed={0,0};
    public volatile int queuePeak;
    public volatile boolean closedOk;
    public final File dir;
    private final LongSupplier clock;
    private final Consumer<String> failure;
    private final ArrayBlockingQueue<Object> queue=new ArrayBlockingQueue<>(4096);
    private volatile boolean closing;
    private final FileOutputStream[] csv=new FileOutputStream[2];
    private FileOutputStream eventStream,anchorStream;
    private final ByteArrayOutputStream[] buffers={new ByteArrayOutputStream(),new ByteArrayOutputStream()};
    private final long[] pending={0,0},lastFlush={0,0};
    public long[] successfulSyncTimes() {return lastFlush.clone();}
    private long logFlush;
    private static final String HEADER="sequence,sensor_timestamp_ns,received_elapsed_realtime_ns,writer_dequeued_elapsed_realtime_ns,x,y,z,accuracy\n";
    private static final class LogEntry {
        final String line;final boolean anchor;
        LogEntry(String s,boolean a){line=s;anchor=a;}
    }
    public SessionFiles(File dir,LongSupplier clock,Consumer<String> failure) {this.dir=dir;this.clock=clock;this.failure=failure;}
    public synchronized void start() {
        if(worker!=null)throw new IllegalStateException("writer already started");
        worker=new Thread(this::run,"imu-file-writer");worker.start();
    }
    public boolean offer(RecordingContract.Sample sample) {
        if(closing || finished)return false;
        boolean ok=queue.offer(sample);queuePeak=Math.max(queuePeak,queue.size());return ok;
    }
    public boolean event(String type,JSONObject details) {
        return log(new LogEntry(Jsons.object("elapsed_ns",clock.getAsLong(),"type",type,"details",details).toString()+"\n",false));
    }
    public boolean anchor(long planned,long before,long wall,long after) {
        return log(new LogEntry(planned+","+before+","+wall+","+after+"\n",true));
    }
    private boolean log(LogEntry e) {
        if(closing || finished)return false;
        if(queue.offer(e))return true;
        failure.accept("event_queue_overflow");return false;
    }
    public void requestClose() {closing=true;}
    public static boolean shouldFlush(int bytes,long age) {return bytes>0 && (bytes>=65536 || age>=5_000_000_000L);}
    private void run() {
        try {
            if(!dir.isDirectory() && !dir.mkdirs())throw new IOException("cannot create session directory");
            eventStream=new FileOutputStream(new File(dir,"events.jsonl"));
            anchorStream=new FileOutputStream(new File(dir,"anchors.csv"));
            anchorStream.write("planned_elapsed_ns,elapsed_before_ns,wall_ms,elapsed_after_ns\n".getBytes(StandardCharsets.UTF_8));
            for(int c=0;c<2;c++) {
                csv[c]=new FileOutputStream(new File(dir,RecordingContract.CHANNELS[c]+".csv"));
                csv[c].write(HEADER.getBytes(StandardCharsets.UTF_8));csv[c].flush();csv[c].getFD().sync();lastFlush[c]=clock.getAsLong();
            }
            eventStream.getFD().sync();anchorStream.getFD().sync();logFlush=clock.getAsLong();
            while(!closing || !queue.isEmpty()) {
                Object item=queue.poll(100,TimeUnit.MILLISECONDS);
                if(item instanceof RecordingContract.Sample) {
                    RecordingContract.Sample s=(RecordingContract.Sample)item;s.dequeuedNs=clock.getAsLong();
                    buffers[s.channel].write(s.csv().getBytes(StandardCharsets.UTF_8));pending[s.channel]++;
                } else if(item instanceof LogEntry) {
                    LogEntry e=(LogEntry)item;(e.anchor?anchorStream:eventStream).write(e.line.getBytes(StandardCharsets.UTF_8));
                }
                long now=clock.getAsLong();
                for(int c=0;c<2;c++)if(shouldFlush(buffers[c].size(),now-lastFlush[c]))flush(c);
                if(now-logFlush>=5_000_000_000L){eventStream.flush();eventStream.getFD().sync();anchorStream.flush();anchorStream.getFD().sync();logFlush=now;}
            }
            for(int c=0;c<2;c++)flush(c);
            eventStream.flush();eventStream.getFD().sync();anchorStream.flush();anchorStream.getFD().sync();
        } catch(Exception e) {error=e.getClass().getSimpleName()+": "+e.getMessage();closing=true;failure.accept("storage_failure");}
        finally {
            boolean clean=true;
            for(FileOutputStream f:new FileOutputStream[]{csv[0],csv[1],eventStream,anchorStream})if(f!=null)try{f.close();}catch(IOException e){clean=false;error="close_failure: "+e.getMessage();}
            closedOk=clean;finished=true;
        }
    }
    private void flush(int c) throws Exception {
        if(buffers[c].size()==0)return;
        int bytes=buffers[c].size();long rows=pending[c],start=clock.getAsLong(),writeEnd=0,flushEnd=0,syncEnd=0;
        String result="failed";
        try {
            buffers[c].writeTo(csv[c]);written[c]+=rows;buffers[c].reset();pending[c]=0;writeEnd=clock.getAsLong();
            csv[c].flush();flushEnd=clock.getAsLong();csv[c].getFD().sync();syncEnd=clock.getAsLong();
            confirmed[c]=written[c];lastFlush[c]=syncEnd;result="ok";
        } finally {
            JSONObject m=Jsons.object("channel",RecordingContract.CHANNELS[c],"bytes",bytes,"rows",rows,
                "start_ns",start,"write_end_ns",writeEnd,"flush_end_ns",flushEnd,"sync_end_ns",syncEnd,"result",result);
            eventStream.write((Jsons.object("elapsed_ns",clock.getAsLong(),"type","csv_io","details",m).toString()+"\n").getBytes(StandardCharsets.UTF_8));
        }
    }
}
