"""
Исправления для функциональности поиска по марке автомобиля и сценария покупки одной щетки.
"""

# 1. Исправление для повторного ввода команды /brand и обработки ввода только марки

# В handlers/command_handler.py:

"""
async def brand(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    '''
    Обрабатывает команду /brand для поиска по марке автомобиля.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст обработчика
    '''
    user = update.effective_user
    log_user_action(user.id, user.username, "BRAND_SEARCH")
    
    # Сбрасываем предыдущие состояния ожидания, если они были
    if 'waiting_for_brand' in context.user_data:
        del context.user_data['waiting_for_brand']
    
    # Проверяем, есть ли аргументы команды
    if context.args and len(context.args) > 0:
        # Если есть аргументы, используем их как запрос
        brand_query = ' '.join(context.args)
        await self._handle_brand_search(update, context, brand_query)
    else:
        # Если аргументов нет, просим пользователя ввести марку
        await update.message.reply_text(
            "🚗 <b>Поиск по марке автомобиля</b>\n\n"
            "Пожалуйста, введите марку автомобиля для поиска.\n"
            "Например: <code>BMW</code> или <code>Toyota</code>",
            parse_mode='HTML'
        )
        
        # Устанавливаем флаг ожидания ввода марки
        context.user_data['waiting_for_brand'] = True
"""

# 2. Изменение в handlers/message_handler.py для обработки ввода только марки:

"""
async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    '''
    Обрабатывает текстовые сообщения пользователя.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст обработчика
    '''
    # Проверяем, не ожидается ли ввод марки
    if context.user_data.get('waiting_for_brand'):
        # Сбрасываем флаг ожидания
        del context.user_data['waiting_for_brand']
        # Обрабатываем ввод как поиск по марке
        await self.handle_brand_search(update, context, update.message.text)
        return
        
    # Оригинальный код обработки сообщения
    user = update.effective_user
    self.user_manager.register_user(user.id)
    text = update.message.text.strip()
    context.user_data['user_query_message_id'] = update.message.message_id
    
    # Логирование действия пользователя
    log_user_action(user.id, user.username, "SEARCH", text)
    
    # Отправка индикатора загрузки
    await update.message.chat.send_action("typing")
    
    # Получение синонимов
    synonyms = self.synonym_manager.get_synonyms()
    
    # Функция для логирования отладочной информации
    def log_debug(msg: str) -> None:
        logger.info(f"SEARCH_DEBUG | User: {user.id} | Query: {text!r} | {msg}")
    
    # Проверяем, является ли запрос просто маркой автомобиля (без модели)
    # Это эвристика: если запрос короткий (1-2 слова) и не содержит цифр, 
    # то это, вероятно, только марка
    words = text.split()
    contains_digits = any(char.isdigit() for char in text)
    
    if len(words) <= 2 and not contains_digits:
        # Проверяем, есть ли точное совпадение по марке
        brand_matches = self.db.cars_df[self.db.cars_df['brand'].str.lower() == text.lower()]
        
        # Если есть точное совпадение по марке, обрабатываем как поиск по марке
        if not brand_matches.empty:
            await self.handle_brand_search(update, context, text)
            return
    
    # Поиск автомобилей по обычному запросу
    result = self.search_engine.search(text, synonyms, log_debug=log_debug)
    matches = result['matches']
    similar = result['similar']
    
    # Остальной код метода остается без изменений
    # ...
"""

# 3. Исправление для сценария покупки одной щетки в handlers/callback_handler.py:

"""
async def _handle_single_wiper_selection(self, query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    '''
    Обрабатывает выбор одной щетки.
    
    Args:
        query: Объект callback-запроса
        context: Контекст обработчика
    '''
    type_id = query.data.replace("single_", "")
    store = self.user_manager.get_callback_data(type_id)
    
    if not store:
        await query.message.edit_text(
            text="⚠️ Не удалось найти информацию о выбранной щетке. Пожалуйста, начните поиск заново."
        )
        return
    
    # Создаем кнопки для выбора стороны (водительская/пассажирская)
    buttons = []
    
    # Проверяем наличие размеров для водительской и пассажирской сторон
    driver_size = store.get('driver_size')
    pass_size = store.get('pass_size')
    
    if driver_size:
        buttons.append([InlineKeyboardButton(f"👨‍✈️ Водительская ({driver_size} мм)", 
                                           callback_data=f"single_left_{type_id}")])
    
    if pass_size:
        buttons.append([InlineKeyboardButton(f"👨‍👩‍👧 Пассажирская ({pass_size} мм)", 
                                           callback_data=f"single_right_{type_id}")])
    
    # Кнопка "Назад"
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=f"type_{type_id}")])
    
    # Получение информации об автомобиле
    car_rows = self.db.cars_df[
        (self.db.cars_df['brand'] == store.get('brand', '')) &
        (self.db.cars_df['model'] == store.get('model', '')) &
        (self.db.cars_df['years'] == store.get('years', ''))
    ]
    
    car_info = ""
    if not car_rows.empty:
        car_info = self.db.get_car_info(car_rows.iloc[0])
    
    frame = store.get('gy_frame', '')
    gy_type = store.get('gy_type', '')
    
    # Получение описания типа щетки
    type_desc = ""
    if self.db.types_desc_df is not None:
        type_rows = self.db.types_desc_df[self.db.types_desc_df['gy_type'] == gy_type]
        if not type_rows.empty:
            desc = type_rows.iloc[0].get('description', '')
            if desc:
                type_desc = f"\n\n<i>{desc}</i>"
    
    # Формирование сообщения
    message = (
        f"{car_info}\n"
        f"<b>Выбран тип щётки:</b> <i>{frame} {gy_type}</i>{type_desc}\n\n"
        f"<b>Выберите сторону для покупки одной щётки:</b>"
    )
    
    # Отправка сообщения с кнопками
    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='HTML'
    )

async def _handle_side_selection(self, query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    '''
    Обрабатывает выбор стороны для одной щетки.
    
    Args:
        query: Объект callback-запроса
        context: Контекст обработчика
    '''
    data = query.data
    type_id = data.replace("single_", "")
    store = self.user_manager.get_callback_data(type_id)
    
    if not store:
        await query.message.edit_text(
            text="⚠️ Не удалось найти информацию о выбранной щетке. Пожалуйста, начните поиск заново."
        )
        return
    
    # Перенаправляем на обработку выбора конкретной стороны
    if data.startswith("single_left_") or data.startswith("single_right_"):
        await self._handle_single_wiper_selection(query, context)
    else:
        # Это первичный выбор "Купить одну щетку"
        await self._handle_single_wiper_selection(query, context)
"""

# 4. Дополнительные исправления для обработки выбора конкретной стороны:

"""
async def _handle_single_wiper_side_selection(self, query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    '''
    Обрабатывает выбор конкретной стороны для одной щетки.
    
    Args:
        query: Объект callback-запроса
        context: Контекст обработчика
    '''
    data = query.data
    is_left = data.startswith("single_left_")
    type_id = data.replace("single_left_", "").replace("single_right_", "")
    store = self.user_manager.get_callback_data(type_id)
    
    if not store:
        await query.message.edit_text(
            text="⚠️ Не удалось найти информацию о выбранной щетке. Пожалуйста, начните поиск заново."
        )
        return
    
    frame = store.get('gy_frame', '')
    gy_type = store.get('gy_type', '')
    mount = store.get('mount', '')
    
    # Определяем размер в зависимости от выбранной стороны
    size = store.get('driver_size') if is_left else store.get('pass_size')
    side_name = "Водительская" if is_left else "Пассажирская"
    
    if not size:
        await query.message.edit_text(
            text=f"⚠️ Не удалось найти размер для {side_name.lower()} стороны. Пожалуйста, выберите другую сторону."
        )
        return
    
    # Получение ссылок на щетку выбранной стороны
    ozon_url, wb_url = self.db.get_single_wiper_links(frame, gy_type, mount, size)
    
    # Получение информации об автомобиле
    car_rows = self.db.cars_df[
        (self.db.cars_df['brand'] == store.get('brand', '')) &
        (self.db.cars_df['model'] == store.get('model', '')) &
        (self.db.cars_df['years'] == store.get('years', ''))
    ]
    
    car_info = ""
    if not car_rows.empty:
        car_info = self.db.get_car_info(car_rows.iloc[0])
    
    # Получение описания типа щетки
    type_desc = ""
    if self.db.types_desc_df is not None:
        type_rows = self.db.types_desc_df[self.db.types_desc_df['gy_type'] == gy_type]
        if not type_rows.empty:
            desc = type_rows.iloc[0].get('description', '')
            if desc:
                type_desc = f"\n\n<i>{desc}</i>"
    
    # Формирование сообщения
    message = (
        f"{car_info}\n"
        f"<b>Выбран тип щётки:</b> <i>{frame} {gy_type}</i>{type_desc}\n\n"
        f"<b>{side_name} щётка ({size} мм)</b>\n\n"
        f"<b>Выберите магазин для покупки:</b>"
    )
    
    # Создание кнопок
    buttons = []
    
    if ozon_url and isinstance(ozon_url, str) and ozon_url.startswith("http"):
        buttons.append([InlineKeyboardButton("🌐 Купить на Ozon", url=ozon_url)])
    
    if wb_url and isinstance(wb_url, str) and wb_url.startswith("http"):
        buttons.append([InlineKeyboardButton("🟣 Купить на Wildberries", url=wb_url)])
    
    # Кнопка "Назад"
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=f"single_{type_id}")])
    
    # Отправка сообщения с кнопками
    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='HTML'
    )
"""

# 5. Обновление метода handle_callback_query для обработки новых callback-запросов:

"""
async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает callback-запросы.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст обработчика
    """
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        if not hasattr(query, 'data') or not query.data:
            return
        
        data = query.data
        log_user_action(user.id, user.username, "BUTTON_CLICK", data)
        
        # Обработка различных типов callback-запросов
        if data.startswith("model_"):
            await self._handle_model_selection(query, context)
        elif data.startswith("frame_"):
            await self._handle_frame_selection(query, context)
        elif data.startswith("type_"):
            await self._handle_type_selection(query, context)
        elif data.startswith("kit_"):
            await self._handle_kit_selection(query, context)
        elif data.startswith("single_left_") or data.startswith("single_right_"):
            await self._handle_single_wiper_side_selection(query, context)
        elif data.startswith("single_"):
            await self._handle_single_wiper_selection(query, context)
        elif data == "new_search":
            await self._handle_new_search(query, context)
        elif data.startswith("back_to_frames_"):
            await self._handle_back_to_frames(query, context)
        elif data.startswith("back_to_types_"):
            await self._handle_back_to_types(query, context)
        elif data.startswith("add_favorite_"):
            await self._handle_add_favorite(query, context)
        elif data.startswith("view_favorites"):
            await self._handle_view_favorites(query, context)
        elif data.startswith("remove_favorite_"):
            await self._handle_remove_favorite(query, context)
        elif data.startswith("page_"):
            await self._handle_pagination(query, context)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки: {str(e)}")
        log_user_action(user.id, user.username, "BUTTON_ERROR", getattr(query, "data", ""), str(e))
        try:
            await query.edit_message_text(
                text="😔 Произошла ошибка при получении информации. Попробуйте ещё раз✨"
            )
        except Exception:
            pass
"""

# 6. Добавление метода в Database для получения ссылок на одну щетку:

"""
def get_single_wiper_links(self, frame: str, gy_type: str, mount: str, size: int) -> Tuple[Optional[str], Optional[str]]:
    '''
    Получает ссылки на одну щетку определенного размера.
    
    Args:
        frame: Тип корпуса щетки
        gy_type: Вид щетки
        mount: Тип крепления
        size: Размер щетки
        
    Returns:
        Tuple[Optional[str], Optional[str]]: Ссылки на Ozon и Wildberries
    '''
    if self.wipers_df is None:
        return None, None
    
    # Фильтрация по типу корпуса, виду щетки и размеру
    wipers = self.wipers_df[
        (self.wipers_df['gy_frame'] == frame) &
        (self.wipers_df['gy_type'] == gy_type) &
        (self.wipers_df['size'] == size)
    ]
    
    # Если нет точного совпадения по размеру, ищем ближайший размер
    if wipers.empty and isinstance(size, (int, float)):
        size_int = int(size)
        # Находим ближайший размер (в пределах ±10 мм)
        for delta in range(1, 11):
            wipers_plus = self.wipers_df[
                (self.wipers_df['gy_frame'] == frame) &
                (self.wipers_df['gy_type'] == gy_type) &
                (self.wipers_df['size'] == size_int + delta)
            ]
            wipers_minus = self.wipers_df[
                (self.wipers_df['gy_frame'] == frame) &
                (self.wipers_df['gy_type'] == gy_type) &
                (self.wipers_df['size'] == size_int - delta)
            ]
            
            if not wipers_plus.empty:
                wipers = wipers_plus
                break
            elif not wipers_minus.empty:
                wipers = wipers_minus
                break
    
    if wipers.empty:
        return None, None
    
    # Получение ссылок
    ozon_url = None
    wb_url = None
    
    for _, wiper in wipers.iterrows():
        if pd.notna(wiper.get('ozon_url')) and not ozon_url:
            ozon_url = wiper['ozon_url']
        if pd.notna(wiper.get('wb_url')) and not wb_url:
            wb_url = wiper['wb_url']
        
        if ozon_url and wb_url:
            break
    
    return ozon_url, wb_url
"""
