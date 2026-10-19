package org.imulayout.recorder.core;

/** Immutable user request, never a promise of the sensor's actual event rate. */
public final class RecordingConfig {
    public static final int DEFAULT_RATE_HZ=100;
    public final int requestedRateHz,periodUs;
    private RecordingConfig(int hz){requestedRateHz=hz;periodUs=(int)Math.round(1_000_000d/hz);}
    public static RecordingConfig of(int hz) {
        if(hz<25||hz>200)throw new IllegalArgumentException("请输入25–200之间的整数Hz");
        return new RecordingConfig(hz);
    }
    public static RecordingConfig fromText(String text) {
        String value=text==null?"":text.trim();
        if(!value.matches("[0-9]+"))throw new IllegalArgumentException("请输入25–200之间的整数Hz");
        try{return of(Integer.parseInt(value));}catch(NumberFormatException e){throw new IllegalArgumentException("请输入25–200之间的整数Hz");}
    }
    public void validateSensor(String name,int minDelayUs,int maxDelayUs) {
        if((minDelayUs>0&&periodUs<minDelayUs)||(maxDelayUs>0&&periodUs>maxDelayUs))
            throw new IllegalArgumentException(name+"的已报告能力不支持此请求周期（"+periodUs+" µs）");
    }
}
