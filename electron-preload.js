const {
    contextBridge,
    ipcRenderer,
} = require("electron");

contextBridge.exposeInMainWorld(
    "aliceDesktop",
    {
        minimize: () =>
            ipcRenderer.invoke(
                "alice:minimize"
            ),

        close: () =>
            ipcRenderer.invoke(
                "alice:close"
            ),
    }
);