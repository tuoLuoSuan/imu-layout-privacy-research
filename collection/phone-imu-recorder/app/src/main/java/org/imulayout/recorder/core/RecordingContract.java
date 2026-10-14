package org.imulayout.recorder.core;
public final class RecordingContract {
    private RecordingContract() {}
    public static final long MAX_DURATION_NS=2_700_000_000_000L,DRAIN_TIMEOUT_NS=30_000_000_000L;
    public static final int QUEUE_CAPACITY=4096,FLUSH_BYTES=65536;
    public static final long FLUSH_NS=5_000_000_000L;
    public static final String[] CHANNELS={"accelerometer","gyroscope"};
    public static final class Sample {
        public final int channel,accuracy;
        public final long sequence,eventNs,receivedNs;
        public long dequeuedNs;
        public final float x,y,z;
        public Sample(int c,long seq,long e,long r,float a,float b,float d,int status) {
            channel=c;sequence=seq;eventNs=e;receivedNs=r;x=a;y=b;z=d;accuracy=status;
        }
        public String csv() {return sequence+","+eventNs+","+receivedNs+","+dequeuedNs+","+x+","+y+","+z+","+accuracy+"\n";}
    }
}
