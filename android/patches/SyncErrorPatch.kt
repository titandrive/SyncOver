package app.syncover.patches

import app.morphe.patcher.patch.AppTarget
import app.morphe.patcher.patch.Compatibility
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.patcher.extensions.InstructionExtensions.addInstructions

@Suppress("unused")
val syncErrorNotifications = bytecodePatch(
    name = "SyncOver sync-error notifications",
    description = "Alerts after sync errors persist for two minutes, suppresses duplicates, and reports recovery. Uses existing Syncthing events.",
    default = false,
) {
    compatibleWith(Compatibility(name = "Syncthing-Fork", packageName = "com.github.catfriend1.syncthingfork",
        targets = listOf(AppTarget(version = "2.1.6.0"))))
    extendWith("syncover/alerts.dex")
    execute {
        val owner = mutableClassDefBy("Lcom/nutomic/syncthingandroid/service/EventProcessor;")
        require(owner.instanceFields.any { it.name == "mContext" && it.type == "Landroid/content/Context;" }) {
            "EventProcessor's context field changed; refusing an incompatible APK."
        }
        val event = owner.methods.single { it.name == "onEvent" && it.parameterTypes == listOf(
            "Lcom/nutomic/syncthingandroid/model/Event;", "Lcom/google/gson/JsonElement;") }
        event.addInstructions(0, "invoke-static/range {p0 .. p2}, Lapp/syncover/patch/SyncAlerts;->onEvent(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)V")
        owner.methods.single { it.name == "stop" && it.parameterTypes.isEmpty() }.addInstructions(0,
            "invoke-static/range {p0 .. p0}, Lapp/syncover/patch/SyncAlerts;->stopped(Ljava/lang/Object;)V")
    }
}
