package org.imulayout.recorder.ui;

import android.app.Activity;
import android.app.AlertDialog;
import android.text.InputType;
import android.view.View;
import android.widget.*;
import java.util.function.Consumer;
import java.util.Locale;
import org.imulayout.recorder.R;
import org.imulayout.recorder.core.RecordingConfig;

/** Small native editor; persistence and session ownership stay with the caller. */
public final class FrequencyDialog {
    private FrequencyDialog(){}
    public static void show(Activity activity,RecordingConfig selected,Consumer<RecordingConfig> save) {
        int space=Math.round(20*activity.getResources().getDisplayMetrics().density);
        LinearLayout panel=new LinearLayout(activity);panel.setOrientation(LinearLayout.VERTICAL);panel.setPadding(space,space/2,space,0);
        TextView label=new TextView(activity);label.setText(R.string.frequency_input_label);panel.addView(label);
        EditText input=new EditText(activity);input.setId(View.generateViewId());label.setLabelFor(input.getId());
        input.setInputType(InputType.TYPE_CLASS_NUMBER);input.setSingleLine(true);input.setText(String.format(Locale.ROOT,"%d",selected.requestedRateHz));
        panel.addView(input,new LinearLayout.LayoutParams(-1,-2));
        LinearLayout presets=new LinearLayout(activity);
        for(int hz:new int[]{25,50,100,200}) {
            Button button=new Button(activity);button.setText(String.format(Locale.ROOT,"%d",hz));button.setMinWidth(0);button.setPadding(0,0,0,0);
            button.setContentDescription(activity.getString(R.string.frequency_preset,hz));
            button.setOnClickListener(v->{input.setText(String.format(Locale.ROOT,"%d",hz));input.setSelection(input.length());});
            presets.addView(button,new LinearLayout.LayoutParams(0,-2,1));
        }
        panel.addView(presets);
        TextView note=new TextView(activity);note.setText(R.string.frequency_explanation);note.setTextSize(14);note.setPadding(0,space/2,0,space);panel.addView(note);
        ScrollView scroll=new ScrollView(activity);scroll.addView(panel);
        AlertDialog dialog=new AlertDialog.Builder(activity).setTitle(R.string.frequency_title).setView(scroll)
            .setNegativeButton(android.R.string.cancel,null).setPositiveButton(R.string.save_settings,null).create();
        dialog.setOnShowListener(ignored->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            try{RecordingConfig config=RecordingConfig.fromText(input.getText().toString());save.accept(config);dialog.dismiss();}
            catch(IllegalArgumentException e){input.setError(e.getMessage());}
        }));
        dialog.show();
    }
}
