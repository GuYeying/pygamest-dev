package pygamestdev;

import android.content.Context;
import android.text.InputType;
import android.view.inputmethod.InputConnection;
import android.view.SurfaceView;
import android.view.inputmethod.BaseInputConnection;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;

/** 文本输入承载 SurfaceView：声明为文本编辑器（IME 可附着——软键盘
 *  呼出的前置条件：View 可聚焦 + onCheckIsTextEditor=true + 有
 *  InputConnection），IME 提交文本经 commitText → JNI injectText
 *  （TextInput 事件链，与触摸注入同构）。 */
class TextInputSurfaceView extends SurfaceView {
    private final TextSink sink;

    interface TextSink { void onText(String text); void onDelete(); }

    TextInputSurfaceView(Context ctx, TextSink sink) {
        super(ctx);
        this.sink = sink;
        // FOCUSABLE（非 touch-mode）= 程序性 requestFocus 的前提——
        // showSoftInput 要求 served view 持有焦点；**不开**
        // focusableInTouchMode：点按自动聚焦→IMM 自动挂输入法（点哪
        // 都弹键盘）的元凶，弹收全权交给 isTextInputWanted 轮询
        setFocusable(FOCUSABLE);
    }

    @Override
    public boolean onCheckIsTextEditor() { return true; }

    @Override
    public InputConnection onCreateInputConnection(EditorInfo outAttrs) {
        outAttrs.inputType = InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS;
        outAttrs.imeOptions = EditorInfo.IME_FLAG_NO_FULLSCREEN
                | EditorInfo.IME_ACTION_DONE;
        return new BaseInputConnection(this, false) {
            @Override
            public boolean commitText(CharSequence text, int newCursorPosition) {
                sink.onText(text.toString());
                return true;
            }
            @Override
            public boolean deleteSurroundingText(int beforeLength, int afterLength) {
                PygameRsDev.injectBackspace();
                return true;
            }
            @Override
            public boolean sendKeyEvent(android.view.KeyEvent event) {
                // 退格第二路径：部分输入法删字走 sendKeyEvent(KEYCODE_DEL)
                // 而非 deleteSurroundingText——InputConnection 层直接拦
                // （不依赖 view 焦点分发，卓易通翻译层同吃）。ACTION_DOWN
                // 消费一次防双删，其余按键放行默认分发
                if (event.getAction() == android.view.KeyEvent.ACTION_DOWN
                        && event.getKeyCode() == android.view.KeyEvent.KEYCODE_DEL) {
                    PygameRsDev.injectBackspace();
                    return true;
                }
                return super.sendKeyEvent(event);
            }
        };
    }

    @Override
    public boolean onKeyDown(int keyCode, android.view.KeyEvent event) {
        // KEYCODE_DEL = 软键盘/实体键盘的退格路径（不走 InputConnection）
        if (keyCode == android.view.KeyEvent.KEYCODE_DEL) {
            sink.onDelete();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }
}