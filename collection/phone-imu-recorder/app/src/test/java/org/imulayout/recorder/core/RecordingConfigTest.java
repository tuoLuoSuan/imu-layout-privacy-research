package org.imulayout.recorder.core;

import org.junit.Test;
import static org.junit.Assert.*;

public class RecordingConfigTest {
    @Test public void selectedHzProducesAnImmutableRoundedPeriod() {
        RecordingConfig first=RecordingConfig.fromText(" 120 ");
        RecordingConfig second=RecordingConfig.of(25);
        assertEquals(120,first.requestedRateHz);assertEquals(8333,first.periodUs);
        assertEquals(40000,second.periodUs);assertEquals(8333,first.periodUs);
        assertEquals(10000,RecordingConfig.of(100).periodUs);
        assertEquals(5000,RecordingConfig.of(200).periodUs);
    }
    @Test public void refusesNonIntegerOrOutOfRangeRates() {
        for(String value:new String[]{""," ","24","201","100.0","1e2","+100","-50","2147483648"}) {
            try{RecordingConfig.fromText(value);fail(value);}catch(IllegalArgumentException expected){}
        }
    }
    @Test public void sensorCapabilitiesRejectInsteadOfClamping() {
        RecordingConfig config=RecordingConfig.of(100);
        config.validateSensor("test",10000,10000);
        config.validateSensor("unknown maximum",5000,0);
        try{config.validateSensor("slow",20000,100000);fail();}catch(IllegalArgumentException expected){assertTrue(expected.getMessage().contains("slow"));}
        try{config.validateSensor("fast",1000,5000);fail();}catch(IllegalArgumentException expected){}
        assertEquals(10000,config.periodUs);
    }
}
