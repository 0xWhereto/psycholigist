"""
Text messages in multiple languages.
"""

TEXTS = {
    "welcome": {
        "ru": """
Привет{name}! 👋

Я — бот психологической поддержки. Я здесь, чтобы выслушать тебя и помочь разобраться в твоих чувствах.

⚠️ **Важно**: Я инструмент поддержки, не настоящий терапевт. Для профессионального сопровождения рекомендую обратиться к психологу.

Выбери действие ниже или просто напиши мне сообщение 💙
""",
        "en": """
Hello{name}! 👋

I'm a psychological support bot. I'm here to listen and help you understand your feelings.

⚠️ **Important**: I'm a support tool, not a real therapist. For professional guidance, I recommend consulting a psychologist.

Choose an action below or just send me a message 💙
""",
        "fr": """
Bonjour{name}! 👋

Je suis un bot de soutien psychologique. Je suis là pour t'écouter et t'aider à comprendre tes émotions.

⚠️ **Important**: Je suis un outil de soutien, pas un vrai thérapeute. Pour un accompagnement professionnel, je te recommande de consulter un psychologue.

Choisis une action ci-dessous ou écris-moi simplement un message 💙
"""
    },
    
    "subscription_prompt": {
        "ru": """
📊 **Тарифы подписки**

Бесплатно: 10 сообщений в день

**С подпиской:**
• Неограниченные сообщения
• История диалогов
• Расширенная поддержка

Выберите план:
""",
        "en": """
📊 **Subscription Plans**

Free: 10 messages per day

**With subscription:**
• Unlimited messages
• Conversation history
• Extended support

Choose a plan:
""",
        "fr": """
📊 **Formules d'abonnement**

Gratuit: 10 messages par jour

**Avec abonnement:**
• Messages illimités
• Historique des conversations
• Support étendu

Choisissez une formule:
"""
    },
    
    "payment_instructions": {
        "ru": """
💳 **Инструкция по оплате**

**План:** {plan_name}
**Сумма:** ${amount:.2f} {currency}

Отправьте оплату на адрес:
`{wallet_address}`

После оплаты нажмите кнопку "Я оплатил(а)".

⏳ Подтверждение обычно занимает до 24 часов.
""",
        "en": """
💳 **Payment Instructions**

**Plan:** {plan_name}
**Amount:** ${amount:.2f} {currency}

Send payment to this address:
`{wallet_address}`

After payment, click "I've paid".

⏳ Confirmation usually takes up to 24 hours.
""",
        "fr": """
💳 **Instructions de paiement**

**Formule:** {plan_name}
**Montant:** ${amount:.2f} {currency}

Envoyez le paiement à cette adresse:
`{wallet_address}`

Après le paiement, cliquez sur "J'ai payé".

⏳ La confirmation prend généralement jusqu'à 24 heures.
"""
    },
    
    "payment_pending": {
        "ru": "⏳ Платёж проверяется автоматически. Как только средства поступят, подписка активируется. Обычно это занимает 1-5 минут.",
        "en": "⏳ Payment is being verified automatically. Once funds arrive, your subscription will be activated. This usually takes 1-5 minutes.",
        "fr": "⏳ Le paiement est vérifié automatiquement. Dès que les fonds arrivent, votre abonnement sera activé. Cela prend généralement 1 à 5 minutes."
    },
    
    "subscription_activated": {
        "ru": """
✅ **Подписка активирована!**

**План:** {plan_name}
**Действует до:** {expires_at}

Приятного использования! 💙
""",
        "en": """
✅ **Subscription activated!**

**Plan:** {plan_name}
**Valid until:** {expires_at}

Enjoy! 💙
""",
        "fr": """
✅ **Abonnement activé!**

**Formule:** {plan_name}
**Valable jusqu'au:** {expires_at}

Bonne utilisation! 💙
"""
    },
    
    "subscription_status": {
        "ru": """
📊 **Статус подписки**

**План:** {plan_name}
**Статус:** {status}
**Действует до:** {expires_at}
**Осталось дней:** {days_remaining}
""",
        "en": """
📊 **Subscription Status**

**Plan:** {plan_name}
**Status:** {status}
**Valid until:** {expires_at}
**Days remaining:** {days_remaining}
""",
        "fr": """
📊 **Statut de l'abonnement**

**Formule:** {plan_name}
**Statut:** {status}
**Valable jusqu'au:** {expires_at}
**Jours restants:** {days_remaining}
"""
    },
    
    "no_subscription": {
        "ru": "У вас нет активной подписки. Используйте /subscribe для оформления.",
        "en": "You don't have an active subscription. Use /subscribe to get one.",
        "fr": "Vous n'avez pas d'abonnement actif. Utilisez /subscribe pour en obtenir un."
    },
    
    "free_limit_reached": {
        "ru": """
⚠️ Вы использовали все бесплатные сообщения на сегодня ({limit}).

Для неограниченного доступа оформите подписку: /subscribe

Или возвращайтесь завтра! 💙
""",
        "en": """
⚠️ You've used all your free messages for today ({limit}).

For unlimited access, get a subscription: /subscribe

Or come back tomorrow! 💙
""",
        "fr": """
⚠️ Vous avez utilisé tous vos messages gratuits pour aujourd'hui ({limit}).

Pour un accès illimité, abonnez-vous: /subscribe

Ou revenez demain! 💙
"""
    },
    
    "conversation_reset": {
        "ru": "✨ Диалог сброшен. Мы можем начать сначала. Как я могу тебе помочь?",
        "en": "✨ Conversation reset. We can start fresh. How can I help you?",
        "fr": "✨ Conversation réinitialisée. Nous pouvons repartir de zéro. Comment puis-je t'aider?"
    },
    
    "error_generic": {
        "ru": "Извини, произошла ошибка. Попробуй ещё раз через минуту.",
        "en": "Sorry, an error occurred. Please try again in a minute.",
        "fr": "Désolé, une erreur s'est produite. Réessaye dans une minute."
    },
    
    "reminder_3_days": {
        "ru": "⏰ Ваша подписка истекает через 3 дня ({expires_at}). Продлите её: /subscribe",
        "en": "⏰ Your subscription expires in 3 days ({expires_at}). Renew it: /subscribe",
        "fr": "⏰ Votre abonnement expire dans 3 jours ({expires_at}). Renouvelez-le: /subscribe"
    },
    
    "reminder_1_day": {
        "ru": "⏰ Ваша подписка истекает завтра ({expires_at}). Продлите её: /subscribe",
        "en": "⏰ Your subscription expires tomorrow ({expires_at}). Renew it: /subscribe",
        "fr": "⏰ Votre abonnement expire demain ({expires_at}). Renouvelez-le: /subscribe"
    },
    
    "reminder_expired": {
        "ru": "⏰ Ваша подписка истекла. У вас есть 3 дня грейс-периода. Продлите: /subscribe",
        "en": "⏰ Your subscription has expired. You have 3 days grace period. Renew: /subscribe",
        "fr": "⏰ Votre abonnement a expiré. Vous avez 3 jours de grâce. Renouvelez: /subscribe"
    }
}


def get_text(key: str, lang: str = "ru", **kwargs) -> str:
    """Получает текст на нужном языке с подстановкой параметров."""
    text_dict = TEXTS.get(key, {})
    text = text_dict.get(lang, text_dict.get("ru", f"[Missing text: {key}]"))
    
    try:
        return text.format(**kwargs)
    except KeyError:
        return text
