# VØRTΞX Bot — Translation Strings (العربية + English)
# Usage: lang.get(guild_lang, "key") -> str

TRANSLATIONS = {
    "en": {
        # ── General ──
        "no_permission": "❌ You don't have permission!",
        "not_found": "❌ Not found!",
        "success": "✅ Done!",
        "error": "❌ Error occurred!",
        
        # ── Admin ──
        "setup_done": "✅ Settings saved!",
        "config_title": "⚙️ Server Configuration",
        "welcome_channel": "👋 Welcome Channel",
        "ticket_category": "🎫 Ticket Category",
        "admin_role": "🛡️ Admin Role",
        "mod_role": "👮 Mod Role",
        "mod_log": "📝 Mod Log Channel",
        "not_set": "Not set",
        
        # ── Moderation ──
        "warn_title": "⚠️ Warning",
        "warn_dm": "⚠️ You were warned in **{guild}**\nReason: {reason}\nTotal warnings: {count}",
        "auto_ban": "🔨 {member} auto-banned for 3 warnings!",
        "no_warns": "✅ {member} has no warnings!",
        "warns_cleared": "✅ Cleared all warnings for {member}",
        "timeout_set": "🔇 {member} timed out for {minutes} min",
        "timeout_removed": "🔊 Removed timeout from {member}",
        "cannot_mod": "❌ You can't moderate this member!",
        
        # ── Levels ──
        "rank_title": "📊 Level Card",
        "level": "Level",
        "xp": "XP",
        "rank_label": "Rank",
        "leaderboard_title": "🏆 Leaderboard",
        "level_up": "🎉 {member} reached level **{level}**!",
        
        # ── Tickets ──
        "ticket_created": "✅ Ticket created: {channel}",
        "ticket_closed": "✅ Ticket closed!",
        "ticket_exists": "❌ You already have an open ticket!",
        
        # ── Welcome ──
        "welcome_msg": "🎉 Welcome {member} to **{guild}**!",
        "welcome_set": "✅ Welcome channel set!",
        
        # ── Anti-Raid ──
        "raid_detected": "🚨 **RAID DETECTED** — {count} joins in {seconds}s! Lockdown activated!",
        "raid_ended": "✅ Raid mode disabled. Server is safe!",
        "antiraid_toggle": "🛡️ Anti-raid: {status}",
        
        # ── Broadcast ──
        "broadcast_sent": "✅ Sent to **{count}** channels!",
        "no_history": "📭 No broadcast history!",
        
        # ── Custom Commands ──
        "cmd_added": "✅ Command `{name}` added!",
        "cmd_removed": "✅ Command `{name}` removed!",
        "cmd_not_found": "❌ Command `{name}` not found!",
        "no_commands": "📭 No custom commands!",
        
        # ── Language ──
        "lang_set": "✅ Language set to **{lang}**!",
        "lang_prompt": "🌐 Select your language / اختر لغتك",
        
        # ── Help ──
        "help_title": "📖 VØRTΞX Bot v4",
        "help_desc": "**34 Slash Commands** — All synced",
        "help_admin": "🛡️ Admin",
        "help_mod": "😡 Moderation",
        "help_levels": "🎮 Levels",
        "help_tickets": "🎫 Tickets",
        "help_utility": "ℹ️ Utility",
        "help_antiraid": "🛡️ Anti-Raid",
        "help_broadcast": "📢 Broadcast",
        "help_cmds": "📋 Custom Commands",
        "help_roles": "🎭 Reaction Roles",
        "help_welcome": "👋 Welcome",
    },
    "ar": {
        # ── General ──
        "no_permission": "❌ ما عندك صلاحية!",
        "not_found": "❌ ما لقيت!",
        "success": "✅ تم!",
        "error": "❌ صار خطأ!",
        
        # ── Admin ──
        "setup_done": "✅ تم حفظ الإعدادات!",
        "config_title": "⚙️ إعدادات السيرفر",
        "welcome_channel": "👋 روم الترحيب",
        "ticket_category": "🎫 قسم التذاكر",
        "admin_role": "🛡️ رول الأدمن",
        "mod_role": "👮 رول المشرف",
        "mod_log": "📝 روم السجل",
        "not_set": "غير مضبوط",
        
        # ── Moderation ──
        "warn_title": "⚠️ تحذير",
        "warn_dm": "⚠️ تم تحذيرك في **{guild}**\nالسبب: {reason}\nعدد التحذيرات: {count}",
        "auto_ban": "🔨 {member} تم حظره تلقائياً لوصول 3 تحذيرات!",
        "no_warns": "✅ {member} ما عنده تحذيرات!",
        "warns_cleared": "✅ تم مسح تحذيرات {member}",
        "timeout_set": "🔇 تم كتم {member} لمدة {minutes} دقيقة",
        "timeout_removed": "🔊 تم إلغاء الكتم عن {member}",
        "cannot_mod": "❌ ما تقدر تعدي على هذا العضو!",
        
        # ── Levels ──
        "rank_title": "📊 بطاقة الرتبة",
        "level": "المستوى",
        "xp": "نقاط",
        "rank_label": "الترتيب",
        "leaderboard_title": "🏆 لائحة المتصدرين",
        "level_up": "🎉 {member} وصل لـ level **{level}**!",
        
        # ── Tickets ──
        "ticket_created": "✅ تم إنشاء التذكرة: {channel}",
        "ticket_closed": "✅ تم إغلاق التذكرة!",
        "ticket_exists": "❌ عندك تذكرة مفتوحة بالفعل!",
        
        # ── Welcome ──
        "welcome_msg": "🎉 أهلاً {member} في **{guild}**!",
        "welcome_set": "✅ تم ضبط روم الترحيب!",
        
        # ── Anti-Raid ──
        "raid_detected": "🚨 **هجوم رايد** — {count} انضمام في {seconds}ث! تم تفعيل القفل!",
        "raid_ended": "✅ تم إلغاء وضع الحماية. السيرفر آمن!",
        "antiraid_toggle": "🛡️ الحماية من الهجمات: {status}",
        
        # ── Broadcast ──
        "broadcast_sent": "✅ تم الإرسال لـ **{count}** قناة!",
        "no_history": "📭 لا يوجد سجل بث!",
        
        # ── Custom Commands ──
        "cmd_added": "✅ تم إضافة الأمر `{name}`!",
        "cmd_removed": "✅ تم حذف الأمر `{name}`!",
        "cmd_not_found": "❌ الأمر `{name}` غير موجود!",
        "no_commands": "📭 لا توجد أوامر مخصصة!",
        
        # ── Language ──
        "lang_set": "✅ تم ضبط اللغة على **{lang}**!",
        "lang_prompt": "🌐 اختر لغتك / Select your language",
        
        # ── Help ──
        "help_title": "📖 VØRTΞX بوت v4",
        "help_desc": "**34 أمر سلاش** — جميعها متزامنة",
        "help_admin": "🛡️ الإدارة",
        "help_mod": "😡 الإشراف",
        "help_levels": "🎮 المستويات",
        "help_tickets": "🎫 التذاكر",
        "help_utility": "ℹ️ أدوات",
        "help_antiraid": "🛡️ الحماية",
        "help_broadcast": "📢 البث",
        "help_cmds": "📋 الأوامر المخصصة",
        "help_roles": "🎭 الرولات التفاعلية",
        "help_welcome": "👋 الترحيب",
    }
}

def t(lang: str, key: str, **kwargs) -> str:
    """Get translated string"""
    text = TRANSLATIONS.get(lang, TRANSLATIONS["ar"]).get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text
