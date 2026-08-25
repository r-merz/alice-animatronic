const {
    app,
    BrowserWindow,
    ipcMain,
} = require("electron");

const path = require("path");

let mainWindow = null;

function createAliceWindow() {
    mainWindow = new BrowserWindow({
        width: 1280,
        height: 800,
        minWidth: 640,
        minHeight: 400,

        frame: false,
        transparent: false,
        backgroundColor: "#020617",

        webPreferences: {
            preload: path.join(
                __dirname,
                "electron-preload.js"
            ),

            contextIsolation: true,
            nodeIntegration: false,
            sandbox: true,
        },
    });

    mainWindow.loadURL(
        "http://127.0.0.1:8765/"
    );

    mainWindow.on(
        "closed",
        () => {
            mainWindow = null;
        }
    );
}

ipcMain.handle(
    "alice:minimize",
    () => {
        mainWindow?.minimize();
        return true;
    }
);

ipcMain.handle(
    "alice:close",
    () => {
        mainWindow?.close();
        return true;
    }
);

app.whenReady().then(
    createAliceWindow
);

app.on(
    "window-all-closed",
    () => {
        if (process.platform !== "darwin") {
            app.quit();
        }
    }
);

app.on(
    "activate",
    () => {
        if (!mainWindow) {
            createAliceWindow();
        }
    }
);