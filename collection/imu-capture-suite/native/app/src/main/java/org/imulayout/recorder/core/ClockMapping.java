package org.imulayout.recorder.core;
import java.util.ArrayList;
import java.util.List;
public final class ClockMapping {
    public static final class Anchor {
        public final long before,wallMs,after;
        public Anchor(long b,long w,long a) {before=b;wallMs=w;after=a;}
        public boolean valid() {return after>before && after-before<=5_000_000L;}
        public long midpoint() {return before+(after-before)/2;}
    }
    public static final class Interval {
        public long start,end;
        public String reason;
        public Interval(long s,long e,String r) {start=s;end=e;reason=r;}
    }
    public static final class Result {
        public final List<Interval> mapped=new ArrayList<>(),unmapped=new ArrayList<>();
    }
    public static Result build(List<Anchor> anchors,long start,long end) {
        Result r=new Result();long cursor=start;
        for(int i=1;i<anchors.size();i++) {
            Anchor a=anchors.get(i-1),b=anchors.get(i);
            if(!a.valid() || !b.valid())continue;
            long delta=b.midpoint()-a.midpoint();
            if(delta<=0 || delta>15_000_000_000L
                    || Math.abs((b.wallMs-a.wallMs)-delta/1e6)>100)continue;
            long lo=Math.max(start,a.midpoint()),hi=Math.min(end,b.midpoint());
            if(hi<=lo || lo<cursor)continue;
            if(lo>cursor)r.unmapped.add(new Interval(cursor,lo,"missing_or_invalid_anchor"));
            r.mapped.add(new Interval(lo,hi,"adjacent_valid_anchors"));cursor=hi;
        }
        if(cursor<end)r.unmapped.add(new Interval(cursor,end,"missing_or_invalid_anchor"));
        return r;
    }
}
