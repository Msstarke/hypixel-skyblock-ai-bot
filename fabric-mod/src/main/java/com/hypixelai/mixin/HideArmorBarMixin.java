package com.hypixelai.mixin;

import com.hypixelai.HypixelAIConfig;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.hud.InGameHud;
import net.minecraft.entity.player.PlayerEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(InGameHud.class)
public class HideArmorBarMixin {
    @Inject(method = "renderArmor", at = @At("HEAD"), cancellable = true)
    private static void hideArmorBar(DrawContext context, PlayerEntity player, int i, int j, int k, int l, CallbackInfo ci) {
        if (HypixelAIConfig.isHideArmor()) {
            ci.cancel();
        }
    }
}
