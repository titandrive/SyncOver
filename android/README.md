# SyncOver Android — Morphe patch

Experimental native Android sync-error notifications for **Syncthing-Fork 2.1.6.0** (`com.github.catfriend1.syncthingfork`). This is a standalone patch bundle, separate from Morphe Catppuccin. No API keys or Pushover account are needed.

## Behavior

- Uses Syncthing-Fork's existing event processor. Adds no service, network requests, wake locks or repeating poller.
- Posts an Android notification after the same errors persist for two minutes while the event processor is running.
- Each folder has its own incident. Unchanged incidents are suppressed; changed errors get a fresh delay. Alert history survives app restarts.
- Recovery requires an idle folder summary reporting zero errors. An idle transition by itself is insufficient.
- Paused folders and scanning/syncing retries do not trigger stale delayed notifications. Pending callbacks are cancelled when the event processor stops.
- Adds a **Sync errors** notification channel. Android must allow notifications for the app and channel.
- Tapping an alert opens Syncthing-Fork. Notifications currently identify folders by ID. No Pushover delivery or settings screen in this first version.

Android can delay callbacks while asleep or stop the process. Alerts therefore are not guaranteed exactly two minutes after an error. On restart, the patch waits for fresh error/status events before trusting saved incidents. Existing errors are detected when Syncthing emits a folder error or summary; the patch does not actively query a startup snapshot. Existing Syncthing-Fork notifications remain in place, so its special low-disk-space alert can appear alongside this patch's alert.

## Use in Morphe

1. Import `syncover-android-0.1.0.mpp` as a local patch bundle in Morphe Manager.
2. Select the original, unpatched Syncthing-Fork **2.1.6.0** APK.
3. Select **SyncOver sync-error notifications** and patch the APK.
4. Install using your normal Morphe signing/install workflow, then permit notifications.

Patching changes the APK signature. An ordinary install cannot replace the original publisher-signed app with a Morphe-signed app. Export Syncthing-Fork's configuration/device identity before replacing an existing installation; uninstalling clears its private data. The exported configuration contains sensitive material. This development task does not uninstall or replace the phone's app. Keep the same Morphe signing key for future patched updates.

## Build and tests

Requires Python 3, JDK 21+ and an Android SDK with build-tools/platforms. Set `JAVA_HOME` and `ANDROID_HOME` if they are not at the default Android Studio locations.

```bash
python3 build.py
```

Build downloads public Morphe Desktop 1.18.0, Kotlin compiler 2.3.21 and JetBrains annotations into `.cache`. It compiles the Android extension, runs the plain-Java incident tests, compiles the Kotlin patch, builds a Manager-compatible MPP with JVM classes and DEX, and checks that Morphe discovers it.

Output: `build/syncover-android-0.1.0.mpp`.

Validation: incident-state tests, extension/patch compilation, Morphe bundle discovery, and applying the patch to the exact APK copied from the phone. On-device runtime notifications have not yet been tested; treat this release as experimental. The test-patched APK is unsigned and not installed.

The patch targets verified method signatures and the `mContext` field, failing if those hooks change. Other app versions are not claimed compatible.
