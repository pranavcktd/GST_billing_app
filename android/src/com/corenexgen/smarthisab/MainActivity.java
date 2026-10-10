package com.corenexgen.smarthisab;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.View;
import android.view.Window;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

/**
 * SmartHisab test app: the web app full screen in a WebView, with the phone features it needs —
 * file downloads (reports, backups, Excel), printing / save as PDF, file and photo uploads, camera
 * (barcode scanning) and the back button. The server address can be changed when it cannot be reached.
 */
public class MainActivity extends Activity {
    private static final int FILE_CHOOSER = 1;
    private static final int CAMERA_PERMISSION = 2;
    private static final String PREFS = "smarthisab";

    private WebView web;
    private ProgressBar progress;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingPermission;
    private boolean errorShown = false;

    // Hooks added to every page: blob downloads go to Android.saveFile, window.print to Android.print.
    private static final String BRIDGE_JS =
        "(function(){if(window.__shBridge)return;window.__shBridge=true;" +
        "var origClick=HTMLAnchorElement.prototype.click;" +
        "HTMLAnchorElement.prototype.click=function(){var h=this.href||'';" +
        "if(this.hasAttribute('download')&&(h.indexOf('blob:')===0||h.indexOf('data:')===0)){var name=this.getAttribute('download')||'download';" +
        "fetch(h).then(function(r){return r.blob();}).then(function(b){var fr=new FileReader();" +
        "fr.onloadend=function(){Android.saveFile(String(fr.result).split(',')[1],name,b.type||'application/octet-stream');};fr.readAsDataURL(b);})" +
        ".catch(function(e){Android.toast('Download failed');});return;}return origClick.apply(this,arguments);};" +
        "window.print=function(){Android.print(document.title||'Document');};})();";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window w = getWindow();
        w.setStatusBarColor(Color.parseColor("#96421f"));

        FrameLayout root = new FrameLayout(this);
        web = new WebView(this);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));
        root.addView(progress, new FrameLayout.LayoutParams(-1, 8));
        setContentView(root);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setSupportZoom(false);
        s.setUserAgentString(s.getUserAgentString() + " SmartHisabApp/1.0");
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);
        web.addJavascriptInterface(new Bridge(), "Android");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                Uri home = Uri.parse(serverUrl());
                String scheme = u.getScheme() == null ? "" : u.getScheme();
                boolean sameSite = (scheme.equals("http") || scheme.equals("https")) && home.getHost() != null
                        && home.getHost().equals(u.getHost());
                if (sameSite) return false;
                // phone, e-mail, WhatsApp, maps and other websites open in their own apps
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception e) { toast("No app can open this link"); }
                return true;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progress.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progress.setVisibility(View.GONE);
                view.evaluateJavascript(BRIDGE_JS, null);
                errorShown = false;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame() && !errorShown) {
                    errorShown = true;
                    askServer("Can't reach the server", "Check that the PC is on, the dev server is running and this phone is on the same Wi-Fi.");
                }
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int p) {
                progress.setProgress(p);
                // pages change without reloading (single-page app): keep the hooks in place
                if (p == 100) view.evaluateJavascript(BRIDGE_JS, null);
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = cb;
                try {
                    startActivityForResult(params.createIntent(), FILE_CHOOSER);
                } catch (Exception e) {
                    fileCallback = null;
                    toast("No app to pick files");
                    return false;
                }
                return true;
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> {
                    if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                        request.grant(request.getResources());
                    } else {
                        pendingPermission = request;
                        requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION);
                    }
                });
            }
        });

        web.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String ua, String disposition, String mime, long length) {
                if (url.startsWith("blob:") || url.startsWith("data:")) return; // handled by the page hook
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                } catch (Exception e) {
                    toast("Cannot download " + URLUtil.guessFileName(url, disposition, mime));
                }
            }
        });

        if (savedInstanceState != null) web.restoreState(savedInstanceState);
        else web.loadUrl(serverUrl());
    }

    private String serverUrl() {
        return getSharedPreferences(PREFS, MODE_PRIVATE).getString("url", BuildConfig.DEFAULT_URL);
    }

    private void askServer(String title, String message) {
        final EditText input = new EditText(this);
        input.setText(serverUrl());
        input.setSingleLine(true);
        new AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(message + "\n\nServer address:")
            .setView(input)
            .setCancelable(false)
            .setPositiveButton("Retry", (d, i) -> {
                String url = input.getText().toString().trim();
                if (!url.startsWith("http")) url = "http://" + url;
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("url", url).apply();
                errorShown = false;
                web.loadUrl(url);
            })
            .setNegativeButton("Close app", (d, i) -> finish())
            .show();
    }

    private void toast(String msg) {
        runOnUiThread(() -> Toast.makeText(this, msg, Toast.LENGTH_LONG).show());
    }

    /** Called from the page (see BRIDGE_JS). */
    private class Bridge {
        @JavascriptInterface
        public void saveFile(String base64, String name, String mime) {
            try {
                byte[] data = Base64.decode(base64, Base64.DEFAULT);
                String safe = name.replaceAll("[\\\\/:*?\"<>|]", "_");
                if (Build.VERSION.SDK_INT >= 29) {
                    ContentValues v = new ContentValues();
                    v.put(MediaStore.Downloads.DISPLAY_NAME, safe);
                    v.put(MediaStore.Downloads.MIME_TYPE, mime);
                    v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/SmartHisab");
                    Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                    try (OutputStream out = getContentResolver().openOutputStream(uri)) { out.write(data); }
                    toast("Saved to Downloads/SmartHisab/" + safe);
                } else {
                    File dir = new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "");
                    dir.mkdirs();
                    File f = new File(dir, safe);
                    try (FileOutputStream out = new FileOutputStream(f)) { out.write(data); }
                    toast("Saved: " + f.getAbsolutePath());
                }
            } catch (Exception e) {
                toast("Could not save the file");
            }
        }

        @JavascriptInterface
        public void print(String title) {
            runOnUiThread(() -> {
                PrintManager pm = (PrintManager) getSystemService(Context.PRINT_SERVICE);
                PrintDocumentAdapter adapter = web.createPrintDocumentAdapter(title);
                pm.print(title, adapter, new PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4).build());
            });
        }

        @JavascriptInterface
        public void toast(String msg) {
            MainActivity.this.toast(msg);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileCallback = null;
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        if (requestCode == CAMERA_PERMISSION && pendingPermission != null) {
            if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) pendingPermission.grant(pendingPermission.getResources());
            else pendingPermission.deny();
            pendingPermission = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }
}
