"""
Обработчик для оценки вагусного профиля в Telegram боте.

Позволяет пользователям:
1. Ввести данные HRV из Kubios (3 замера)
2. Пройти краткую поведенческую самооценку
3. Получить классификацию профиля и интерпретацию
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from bot.services.vagal_profile import (
    VagalProfileClassifier,
    KubiosData,
    BehavioralAssessment,
    ThreePhaseMeasurement,
    VagalState,
)

# Состояния диалога
(
    BASELINE_RMSSD,
    BASELINE_SDNN,
    BASELINE_LFHF,
    BASELINE_HF,
    BASELINE_TP,
    STRESS_RMSSD,
    STRESS_SDNN,
    STRESS_LFHF,
    STRESS_HF,
    STRESS_TP,
    RECOVERY_RMSSD,
    RECOVERY_SDNN,
    RECOVERY_LFHF,
    RECOVERY_HF,
    RECOVERY_TP,
    RECOVERY_TIME,
    BEHAVIORAL_START,
    BEHAVIORAL_EYE,
    BEHAVIORAL_VOICE,
    BEHAVIORAL_FACE,
    BEHAVIORAL_SOCIAL,
    BEHAVIORAL_RELAX,
    BEHAVIORAL_DISSOC,
    SHOW_RESULT,
) = range(24)


# Тексты для бота
INTRO_TEXT = """
🫀 *Оценка вагусного профиля*

Этот инструмент поможет определить ваш регуляционный профиль на основе полевагальной теории.

*Что понадобится:*
• Данные из Kubios HRV (3 замера)
• 5 минут на поведенческую самооценку

*Протокол замеров:*
1️⃣ Baseline — в спокойном состоянии (5 мин)
2️⃣ Stress — думая о неприятном (3 мин)
3️⃣ Recovery — восстановление (5 мин)

Готовы начать?
"""

BASELINE_INTRO = """
📊 *Замер 1: Baseline (покой)*

Введите показатели из Kubios для состояния покоя.
Начнём с RMSSD (мс):
"""

STRESS_INTRO = """
📊 *Замер 2: Stress (негативные мысли)*

Теперь введите показатели при стрессе.
RMSSD (мс):
"""

RECOVERY_INTRO = """
📊 *Замер 3: Recovery (восстановление)*

Последний замер — после восстановления.
RMSSD (мс):
"""


async def start_assessment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало оценки профиля"""
    keyboard = [
        [InlineKeyboardButton("▶️ Начать оценку", callback_data="start_hrv")],
        [InlineKeyboardButton("❓ Что такое HRV?", callback_data="explain_hrv")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        INTRO_TEXT,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return BASELINE_RMSSD


async def explain_hrv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Объяснение HRV показателей"""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    explanation = """
📚 *Краткий гид по показателям HRV*

*RMSSD* (мс) — вариабельность между ударами
• Отражает парасимпатическую активность
• Норма: 25-45 мс (зависит от возраста)

*SDNN* (мс) — общая вариабельность
• Общий показатель адаптивности
• Норма: 40-60 мс

*LF/HF ratio* — баланс систем
• < 1.0 = парасимпатика преобладает
• 1-2 = баланс
• > 2.0 = симпатика преобладает

*HF Power* (мс²) — высокочастотная мощность
• Маркер вагусной активности
• Норма: 200-500 мс²

*Total Power* (мс²) — общая мощность спектра
• Общий резерв регуляции
• Норма: 1000-2500 мс²

Где найти в Kubios:
Results → Time-Domain / Frequency-Domain
    """
    
    keyboard = [[InlineKeyboardButton("▶️ Начать оценку", callback_data="start_hrv")]]
    
    await query.edit_message_text(
        explanation,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BASELINE_RMSSD


async def start_hrv_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало ввода HRV данных"""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    # Инициализируем хранилище данных
    context.user_data['hrv_data'] = {
        'baseline': {},
        'stress': {},
        'recovery': {}
    }
    
    await query.edit_message_text(BASELINE_INTRO, parse_mode="Markdown")
    return BASELINE_RMSSD


async def collect_baseline_rmssd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбор RMSSD baseline"""
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['baseline']['rmssd'] = value
        await update.message.reply_text("SDNN (мс):")
        return BASELINE_SDNN
    except ValueError:
        await update.message.reply_text("❌ Введите число. RMSSD (мс):")
        return BASELINE_RMSSD


async def collect_baseline_sdnn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['baseline']['sdnn'] = value
        await update.message.reply_text("LF/HF ratio:")
        return BASELINE_LFHF
    except ValueError:
        await update.message.reply_text("❌ Введите число. SDNN (мс):")
        return BASELINE_SDNN


async def collect_baseline_lfhf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['baseline']['lf_hf'] = value
        await update.message.reply_text("HF Power (мс²):")
        return BASELINE_HF
    except ValueError:
        await update.message.reply_text("❌ Введите число. LF/HF ratio:")
        return BASELINE_LFHF


async def collect_baseline_hf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['baseline']['hf_power'] = value
        await update.message.reply_text("Total Power (мс²):")
        return BASELINE_TP
    except ValueError:
        await update.message.reply_text("❌ Введите число. HF Power (мс²):")
        return BASELINE_HF


async def collect_baseline_tp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['baseline']['total_power'] = value
        await update.message.reply_text(STRESS_INTRO, parse_mode="Markdown")
        return STRESS_RMSSD
    except ValueError:
        await update.message.reply_text("❌ Введите число. Total Power (мс²):")
        return BASELINE_TP


# Аналогичные функции для stress и recovery...
async def collect_stress_rmssd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['stress']['rmssd'] = value
        await update.message.reply_text("SDNN (мс):")
        return STRESS_SDNN
    except ValueError:
        await update.message.reply_text("❌ Введите число. RMSSD (мс):")
        return STRESS_RMSSD


async def collect_stress_sdnn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['stress']['sdnn'] = value
        await update.message.reply_text("LF/HF ratio:")
        return STRESS_LFHF
    except ValueError:
        await update.message.reply_text("❌ Введите число. SDNN (мс):")
        return STRESS_SDNN


async def collect_stress_lfhf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['stress']['lf_hf'] = value
        await update.message.reply_text("HF Power (мс²):")
        return STRESS_HF
    except ValueError:
        await update.message.reply_text("❌ Введите число. LF/HF ratio:")
        return STRESS_LFHF


async def collect_stress_hf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['stress']['hf_power'] = value
        await update.message.reply_text("Total Power (мс²):")
        return STRESS_TP
    except ValueError:
        await update.message.reply_text("❌ Введите число. HF Power (мс²):")
        return STRESS_HF


async def collect_stress_tp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['stress']['total_power'] = value
        await update.message.reply_text(RECOVERY_INTRO, parse_mode="Markdown")
        return RECOVERY_RMSSD
    except ValueError:
        await update.message.reply_text("❌ Введите число. Total Power (мс²):")
        return STRESS_TP


async def collect_recovery_rmssd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['recovery']['rmssd'] = value
        await update.message.reply_text("SDNN (мс):")
        return RECOVERY_SDNN
    except ValueError:
        await update.message.reply_text("❌ Введите число. RMSSD (мс):")
        return RECOVERY_RMSSD


async def collect_recovery_sdnn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['recovery']['sdnn'] = value
        await update.message.reply_text("LF/HF ratio:")
        return RECOVERY_LFHF
    except ValueError:
        await update.message.reply_text("❌ Введите число. SDNN (мс):")
        return RECOVERY_SDNN


async def collect_recovery_lfhf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['recovery']['lf_hf'] = value
        await update.message.reply_text("HF Power (мс²):")
        return RECOVERY_HF
    except ValueError:
        await update.message.reply_text("❌ Введите число. LF/HF ratio:")
        return RECOVERY_LFHF


async def collect_recovery_hf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['recovery']['hf_power'] = value
        await update.message.reply_text("Total Power (мс²):")
        return RECOVERY_TP
    except ValueError:
        await update.message.reply_text("❌ Введите число. HF Power (мс²):")
        return RECOVERY_HF


async def collect_recovery_tp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['recovery']['total_power'] = value
        await update.message.reply_text(
            "⏱ Сколько секунд заняло восстановление?\n"
            "(время от конца стресс-замера до начала recovery-замера)"
        )
        return RECOVERY_TIME
    except ValueError:
        await update.message.reply_text("❌ Введите число. Total Power (мс²):")
        return RECOVERY_TP


async def collect_recovery_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(',', '.'))
        context.user_data['hrv_data']['recovery_time'] = value
        
        await update.message.reply_text(
            "✅ Данные HRV получены!\n\n"
            "🎭 *Теперь краткая самооценка поведения*\n\n"
            "Оцените по шкале 1-5, как вы обычно выглядите со стороны.",
            parse_mode="Markdown"
        )
        
        keyboard = [
            [InlineKeyboardButton(f"{i}", callback_data=f"eye_{i}") for i in range(1, 6)]
        ]
        await update.message.reply_text(
            "👁 *Зрительный контакт*\n"
            "1 = избегаю, 5 = комфортный контакт",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BEHAVIORAL_EYE
    except ValueError:
        await update.message.reply_text("❌ Введите число секунд:")
        return RECOVERY_TIME


async def collect_behavioral_eye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    value = int(query.data.split('_')[1])
    context.user_data['behavioral'] = {'eye_contact': value}
    
    keyboard = [
        [InlineKeyboardButton(f"{i}", callback_data=f"voice_{i}") for i in range(1, 6)]
    ]
    await query.edit_message_text(
        "🗣 *Голос и интонации*\n"
        "1 = монотонный, 5 = выразительный",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BEHAVIORAL_VOICE


async def collect_behavioral_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    value = int(query.data.split('_')[1])
    context.user_data['behavioral']['voice_prosody'] = value
    
    keyboard = [
        [InlineKeyboardButton(f"{i}", callback_data=f"face_{i}") for i in range(1, 6)]
    ]
    await query.edit_message_text(
        "😊 *Мимика*\n"
        "1 = застывшая, 5 = живая",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BEHAVIORAL_FACE


async def collect_behavioral_face(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    value = int(query.data.split('_')[1])
    context.user_data['behavioral']['facial_expressivity'] = value
    
    keyboard = [
        [InlineKeyboardButton(f"{i}", callback_data=f"social_{i}") for i in range(1, 6)]
    ]
    await query.edit_message_text(
        "🤝 *Социальная вовлечённость*\n"
        "1 = отстранённый, 5 = вовлечённый",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BEHAVIORAL_SOCIAL


async def collect_behavioral_social(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    value = int(query.data.split('_')[1])
    context.user_data['behavioral']['social_engagement'] = value
    
    keyboard = [
        [InlineKeyboardButton(f"{i}", callback_data=f"relax_{i}") for i in range(1, 6)]
    ]
    await query.edit_message_text(
        "🧘 *Расслабленность тела*\n"
        "1 = напряжён, 5 = расслаблен",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BEHAVIORAL_RELAX


async def collect_behavioral_relax(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    value = int(query.data.split('_')[1])
    context.user_data['behavioral']['body_relaxation'] = value
    
    keyboard = [
        [InlineKeyboardButton("Да", callback_data="dissoc_yes")],
        [InlineKeyboardButton("Нет", callback_data="dissoc_no")],
    ]
    await query.edit_message_text(
        "🌫 *Бывает ли ощущение отстранённости/оцепенения при стрессе?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BEHAVIORAL_DISSOC


async def collect_behavioral_dissoc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    context.user_data['behavioral']['reports_dissociation'] = query.data == "dissoc_yes"
    context.user_data['behavioral']['reports_numbness'] = query.data == "dissoc_yes"
    context.user_data['behavioral']['reports_anxiety'] = False
    
    # Теперь классифицируем профиль
    await calculate_and_show_profile(query, context)
    return ConversationHandler.END


async def calculate_and_show_profile(query, context: ContextTypes.DEFAULT_TYPE):
    """Расчёт и отображение профиля"""
    hrv = context.user_data['hrv_data']
    beh = context.user_data['behavioral']
    
    # Создаём объекты данных
    def make_kubios(data: dict) -> KubiosData:
        return KubiosData(
            mean_rr=850,  # Примерное значение
            sdnn=data['sdnn'],
            rmssd=data['rmssd'],
            pnn50=20,  # Примерное
            mean_hr=70,
            vlf_power=data['total_power'] * 0.3,
            lf_power=data['total_power'] * 0.4,
            hf_power=data['hf_power'],
            lf_hf_ratio=data['lf_hf'],
            total_power=data['total_power'],
            sd1=data['rmssd'] * 0.7,
            sd2=data['sdnn'] * 1.2
        )
    
    baseline = make_kubios(hrv['baseline'])
    stress = make_kubios(hrv['stress'])
    recovery = make_kubios(hrv['recovery'])
    
    measurements = ThreePhaseMeasurement(
        baseline=baseline,
        stress=stress,
        recovery=recovery,
        recovery_time_seconds=hrv['recovery_time']
    )
    
    behavioral = BehavioralAssessment(
        eye_contact=beh['eye_contact'],
        voice_prosody=beh['voice_prosody'],
        facial_expressivity=beh['facial_expressivity'],
        social_engagement=beh['social_engagement'],
        body_relaxation=beh['body_relaxation'],
        reports_dissociation=beh.get('reports_dissociation', False),
        reports_numbness=beh.get('reports_numbness', False),
        reports_anxiety=beh.get('reports_anxiety', False)
    )
    
    # Классификация
    classifier = VagalProfileClassifier()
    profile = classifier.classify(measurements, behavioral)
    
    # Формируем результат
    state_names = {
        VagalState.VENTRAL: "Вентральный (V)",
        VagalState.SYMPATHETIC: "Симпатический (S)",
        VagalState.DORSAL: "Дорсальный (D)"
    }
    
    pseudo_note = " *(псевдо)*" if profile.is_pseudo else ""
    
    result = f"""
🎯 *ВАШ ВАГУСНЫЙ ПРОФИЛЬ*

*Формула:* `{profile}`

━━━━━━━━━━━━━━━━━━━━

📊 *Компоненты профиля:*

1️⃣ *Физиологическая доминанта:* {state_names[profile.physiological_dominant]}
   ↳ Реальное состояние нервной системы в покое

2️⃣ *Внешняя презентация:* {state_names[profile.behavioral_presentation]}{pseudo_note}
   ↳ Как вы выглядите со стороны

3️⃣ *Реакция на стресс:* {state_names[profile.stress_response]}
   ↳ Куда "проваливается" система при нагрузке

━━━━━━━━━━━━━━━━━━━━

📈 *Показатели:*
• Скорость восстановления: {profile.recovery_speed_percent:.0f}%
• Индекс реактивности: {profile.reactivity_index:.1f}
• Когерентность профиля: {profile.coherence_score:.0%}

━━━━━━━━━━━━━━━━━━━━

💡 *Интерпретация:*
{profile.get_interpretation()}
"""
    
    await query.edit_message_text(result, parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена диалога"""
    await update.message.reply_text("Оценка отменена.")
    return ConversationHandler.END


def get_vagal_assessment_handler() -> ConversationHandler:
    """Возвращает ConversationHandler для оценки профиля"""
    return ConversationHandler(
        entry_points=[CommandHandler("vagal", start_assessment)],
        states={
            BASELINE_RMSSD: [
                CallbackQueryHandler(start_hrv_input, pattern="^start_hrv$"),
                CallbackQueryHandler(explain_hrv, pattern="^explain_hrv$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_baseline_rmssd),
            ],
            BASELINE_SDNN: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_baseline_sdnn)],
            BASELINE_LFHF: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_baseline_lfhf)],
            BASELINE_HF: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_baseline_hf)],
            BASELINE_TP: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_baseline_tp)],
            STRESS_RMSSD: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_stress_rmssd)],
            STRESS_SDNN: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_stress_sdnn)],
            STRESS_LFHF: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_stress_lfhf)],
            STRESS_HF: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_stress_hf)],
            STRESS_TP: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_stress_tp)],
            RECOVERY_RMSSD: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_recovery_rmssd)],
            RECOVERY_SDNN: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_recovery_sdnn)],
            RECOVERY_LFHF: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_recovery_lfhf)],
            RECOVERY_HF: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_recovery_hf)],
            RECOVERY_TP: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_recovery_tp)],
            RECOVERY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_recovery_time)],
            BEHAVIORAL_EYE: [CallbackQueryHandler(collect_behavioral_eye, pattern="^eye_")],
            BEHAVIORAL_VOICE: [CallbackQueryHandler(collect_behavioral_voice, pattern="^voice_")],
            BEHAVIORAL_FACE: [CallbackQueryHandler(collect_behavioral_face, pattern="^face_")],
            BEHAVIORAL_SOCIAL: [CallbackQueryHandler(collect_behavioral_social, pattern="^social_")],
            BEHAVIORAL_RELAX: [CallbackQueryHandler(collect_behavioral_relax, pattern="^relax_")],
            BEHAVIORAL_DISSOC: [CallbackQueryHandler(collect_behavioral_dissoc, pattern="^dissoc_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
