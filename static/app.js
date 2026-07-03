const tg = window.Telegram?.WebApp;
let token = '';
let paymentMethod = 'crypto';
let discount = 0;
let recipientData = null;
let activeTab = 'buy';
let myUsername = '';
let productType = 'stars';
let selectedMonths = 3;

if (tg) {
    const colors = tg.themeParams;
    document.documentElement.style.setProperty('--tg-bg-color', colors.bg_color || '#17212b');
    document.documentElement.style.setProperty('--tg-text-color', colors.text_color || '#ffffff');
    document.documentElement.style.setProperty('--tg-hint-color', colors.hint_color || '#8b95a1');
    document.documentElement.style.setProperty('--tg-link-color', colors.link_color || '#3390ec');
    document.documentElement.style.setProperty('--tg-button-color', colors.button_color || '#3390ec');
    document.documentElement.style.setProperty('--tg-button-text-color', colors.button_text_color || '#ffffff');
    document.documentElement.style.setProperty('--tg-secondary-bg-color', colors.secondary_bg_color || '#232e3c');
}

if (!tg) {
    document.body.innerHTML = `
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; text-align: center; padding: 20px;">
            <i class="fas fa-exclamation-triangle" style="font-size: 48px; color: #f44336; margin-bottom: 20px;"></i>
            <h2>Ошибка запуска</h2>
            <p style="color: var(--tg-hint-color);">Откройте приложение через Telegram</p>
        </div>
    `;
} else {
    tg.ready();
    tg.expand();
    
    const userId = tg.initDataUnsafe?.user?.id;
    myUsername = tg.initDataUnsafe?.user?.username || '';
    
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    if (tabParam === 'transactions') {
        activeTab = 'transactions';
    }
    
    if (!userId) {
        document.body.innerHTML = `
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; text-align: center; padding: 20px;">
                <i class="fas fa-user-slash" style="font-size: 48px; color: #f44336; margin-bottom: 20px;"></i>
                <h2>Ошибка авторизации</h2>
                <p style="color: var(--tg-hint-color);">Не удалось получить ID пользователя</p>
            </div>
        `;
    } else {
        fetch('/auth', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        })
        .then(res => {
            if (!res.ok) throw new Error('Auth failed');
            return res.json();
        })
        .then(data => {
            token = data.token;
            updatePrice();
            toggleClearButton('recipient', 'clear-recipient');
            toggleClearButton('promo', 'clear-promo');
            
            if (activeTab === 'transactions') {
                switchTab('transactions');
            }
        })
        .catch(err => {
            console.error('Auth error:', err);
            tg.showAlert('Ошибка авторизации. Попробуйте перезапустить приложение.');
        });
    }
}

function setMyself() {
    if (myUsername) {
        document.getElementById('recipient').value = myUsername;
        document.getElementById('recipient').dispatchEvent(new Event('input'));
    } else {
        tg.showAlert('Username не найден в вашем профиле Telegram');
    }
}

function togglePromo() {
    const block = document.getElementById('promo-block');
    block.style.display = block.style.display === 'none' ? 'block' : 'none';
}

function showOrderDetail(orderId) {
    fetch(`/order/${orderId}`, {
        headers: {'Authorization': `Bearer ${token}`}
    })
    .then(res => {
        if (!res.ok) throw new Error('Failed to load order');
        return res.json();
    })
    .then(order => {
        const detail = document.getElementById('order-detail');
        
        const statusIcon = order.status === 'pending' 
            ? '<i class="fas fa-clock" style="color: #ffa500;"></i>'
            : order.status === 'completed'
            ? '<i class="fas fa-check-circle" style="color: #4caf50;"></i>'
            : '<i class="fas fa-times-circle" style="color: #f44336;"></i>';
        
        const statusText = order.status === 'pending' ? 'Ожидание оплаты' 
            : order.status === 'completed' ? 'Завершено' 
            : 'Отменено';
        
        const productText = order.product_type === 'stars' 
            ? `<i class="fas fa-star"></i> ${order.stars} звёзд` 
            : `<i class="fas fa-crown"></i> Premium ${order.months} мес`;
        
        detail.innerHTML = `
            <div class="order-card">
                <div class="order-status ${order.status}">
                    ${statusIcon}
                    <span>${statusText}</span>
                </div>
                <div class="order-info-row">
                    <span><i class="fas fa-hashtag"></i> Заказ:</span>
                    <span class="order-hash">#${order.order_id}</span>
                </div>
                <div class="order-info-row">
                    <span><i class="fas fa-box"></i> Товар:</span>
                    <span>${productText}</span>
                </div>
                <div class="order-info-row">
                    <span><i class="fas fa-user"></i> Получатель:</span>
                    <span><i class="fas fa-at"></i> ${order.recipient}</span>
                </div>
                <div class="order-info-row">
                    <span><i class="fas fa-ruble-sign"></i> Сумма:</span>
                    <span>${order.total}₽</span>
                </div>
                <div class="order-info-row">
                    <span><i class="fas fa-calendar"></i> Дата:</span>
                    <span>${new Date(order.created_at).toLocaleString('ru')}</span>
                </div>
            </div>
            <button class="buy-btn" onclick="switchTab('transactions')">
                <i class="fas fa-arrow-left"></i> Назад к транзакциям
            </button>
        `;
        switchTab('order-detail');
    })
    .catch(err => {
        tg.showAlert('Ошибка загрузки заказа');
        console.error(err);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

let recipientTimeout = null;

function toggleClearButton(inputId, btnId) {
    const input = document.getElementById(inputId);
    const btn = document.getElementById(btnId);
    if (input && btn) {
        if (input.value.trim()) {
            btn.style.display = 'flex';
            btn.classList.add('visible');
        } else {
            btn.style.display = 'none';
            btn.classList.remove('visible');
        }
    }
}

function clearRecipient() {
    const input = document.getElementById('recipient');
    input.value = '';
    input.focus();
    document.getElementById('recipient-preview').style.display = 'none';
    recipientData = null;
    toggleClearButton('recipient', 'clear-recipient');
}

function clearPromo() {
    const input = document.getElementById('promo');
    input.value = '';
    input.focus();
    discount = 0;
    document.getElementById('discount-row').style.display = 'none';
    toggleClearButton('promo', 'clear-promo');
    updatePrice();
}

document.getElementById('recipient').addEventListener('input', (e) => {
    const username = e.target.value.replace('@', '').trim();
    
    toggleClearButton('recipient', 'clear-recipient');
    
    if (recipientTimeout) {
        clearTimeout(recipientTimeout);
    }
    
    if (username.length >= 3 && token) {
        document.getElementById('recipient-preview').style.display = 'flex';
        document.getElementById('recipient-avatar').innerHTML = '<i class="fas fa-spinner fa-spin fa-2x"></i>';
        document.getElementById('recipient-name').textContent = 'Проверка...';
        document.getElementById('recipient-username').textContent = '';
        
        recipientTimeout = setTimeout(() => checkRecipient(username), 500);
    } else {
        document.getElementById('recipient-preview').style.display = 'none';
        recipientData = null;
    }
});

document.getElementById('promo').addEventListener('input', (e) => {
    toggleClearButton('promo', 'clear-promo');
});

function switchTab(tab) {
    activeTab = tab;
    document.getElementById('buy-tab').style.display = tab === 'buy' ? 'block' : 'none';
    document.getElementById('transactions-tab').style.display = tab === 'transactions' ? 'block' : 'none';
    document.getElementById('order-detail-tab').style.display = tab === 'order-detail' ? 'block' : 'none';
    
    document.querySelectorAll('.tab-item').forEach((el, i) => {
        el.classList.toggle('active', (i === 0 && tab === 'buy') || (i === 1 && tab === 'transactions'));
    });
    
    if (tab === 'transactions') {
        loadTransactions();
    }
}

function loadTransactions() {
    fetch('/transactions', {
        headers: {'Authorization': `Bearer ${token}`}
    })
    .then(res => {
        if (!res.ok) throw new Error('Failed to load transactions');
        return res.json();
    })
    .then(data => {
        const list = document.getElementById('transactions-list');
        if (data.transactions.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox" style="font-size: 48px; opacity: 0.3; margin-bottom: 12px;"></i>
                    <div>Нет транзакций</div>
                </div>
            `;
        } else {
            list.innerHTML = data.transactions.map(tx => {
                const statusText = tx.status === 'pending' ? 'Ожидание' 
                    : tx.status === 'completed' ? 'Завершено' 
                    : 'Отменено';
                
                const productText = tx.product_type === 'stars' 
                    ? `<i class="fas fa-star"></i> ${tx.stars} звёзд` 
                    : `<i class="fas fa-crown"></i> Premium ${tx.months} мес`;
                
                return `
                    <div class="transaction-item" onclick="showOrderDetail(${tx.order_id})">
                        <div class="transaction-header">
                            <span>${productText}</span>
                            <span class="transaction-status ${tx.status}">${statusText}</span>
                        </div>
                        <div class="transaction-details">
                            <div><i class="fas fa-user"></i> Получатель: @${tx.recipient}</div>
                            <div><i class="fas fa-ruble-sign"></i> Сумма: ${tx.total}₽</div>
                            <div><i class="fas fa-calendar"></i> Дата: ${new Date(tx.created_at).toLocaleString('ru')}</div>
                        </div>
                    </div>
                `;
            }).join('');
        }
    })
    .catch(err => {
        const list = document.getElementById('transactions-list');
        list.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-circle" style="font-size: 48px; opacity: 0.3; margin-bottom: 12px;"></i>
                <div>Ошибка загрузки транзакций</div>
            </div>
        `;
        console.error(err);
    });
}

function checkRecipient(username) {
    fetch(`/check-recipient?username=${encodeURIComponent(username)}&product_type=${productType}`, {
        headers: {'Authorization': `Bearer ${token}`}
    })
    .then(res => {
        if (!res.ok) throw new Error('Failed to check recipient');
        return res.json();
    })
    .then(data => {
        if (data.valid) {
            recipientData = data;
            document.getElementById('recipient-name').textContent = data.name;
            document.getElementById('recipient-username').textContent = '@' + data.username;
            if (data.photo) {
                document.getElementById('recipient-avatar').innerHTML = `<img src="${data.photo}" alt="Avatar">`;
            } else {
                document.getElementById('recipient-avatar').innerHTML = `<i class="fas fa-user fa-2x"></i>`;
            }
            document.getElementById('recipient-preview').style.display = 'flex';
        } else {
            document.getElementById('recipient-preview').style.display = 'none';
            recipientData = null;
        }
    })
    .catch(() => {
        document.getElementById('recipient-preview').style.display = 'none';
        recipientData = null;
    });
}

function selectProduct(type) {
    productType = type;
    document.getElementById('btn-stars').classList.toggle('active', type === 'stars');
    document.getElementById('btn-premium').classList.toggle('active', type === 'premium');
    
    document.getElementById('stars-input').style.display = type === 'stars' ? 'block' : 'none';
    document.getElementById('premium-input').style.display = type === 'premium' ? 'block' : 'none';
    
    if (type === 'premium') {
        updatePremiumPrice();
    } else {
        updatePrice();
    }
}

function selectMonths(months) {
    selectedMonths = months;
    document.querySelectorAll('.month-btn').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.months) === months);
    });
    updatePremiumPrice();
}

function updatePremiumPrice() {
    if (!token) return;
    
    fetch(`/get-price?product_type=premium&months=${selectedMonths}`)
        .then(res => {
            if (!res.ok) throw new Error('Failed to get price');
            return res.json();
        })
        .then(data => {
            let price = data.price_rub;
            const total = price - discount;
            document.getElementById('total').textContent = total.toFixed(2) + '₽';
        })
        .catch(err => {
            console.error('Price update error:', err);
        });
}

function updatePrice() {
    const stars = parseInt(document.getElementById('stars').value) || 50;
    if (stars >= 50 && stars <= 4999 && token) {
        fetch(`/get-price?product_type=stars&stars=${stars}`)
            .then(res => {
                if (!res.ok) throw new Error('Failed to get price');
                return res.json();
            })
            .then(data => {
                let price = data.price_rub;
                const total = price - discount;
                document.getElementById('total').textContent = total.toFixed(2) + '₽';
            })
            .catch(err => {
                console.error('Price update error:', err);
            });
    }
}

function applyPromo() {
    const promo = document.getElementById('promo').value.trim();
    
    if (!promo) {
        tg.showAlert('Введите промокод');
        return;
    }
    
    const promoBtn = document.querySelector('.promo-btn');
    const originalText = promoBtn.textContent;
    promoBtn.disabled = true;
    promoBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    fetch(`/check-promo?code=${encodeURIComponent(promo)}`)
        .then(res => {
            if (!res.ok) throw new Error('Failed to check promo');
            return res.json();
        })
        .then(data => {
            if (data.valid) {
                discount = data.discount;
                document.getElementById('discount').textContent = '-' + discount.toFixed(2) + '₽';
                document.getElementById('discount-row').style.display = 'flex';
                tg.showAlert(`Промокод применен! Скидка ${discount}₽`);
                if (productType === 'stars') {
                    updatePrice();
                } else {
                    updatePremiumPrice();
                }
                document.getElementById('promo-block').style.display = 'none';
            } else {
                tg.showAlert('Промокод недействителен');
            }
        })
        .catch(err => {
            tg.showAlert('Ошибка проверки промокода');
            console.error(err);
        })
        .finally(() => {
            promoBtn.disabled = false;
            promoBtn.textContent = originalText;
        });
}

function handleBuy() {
    if (!recipientData) {
        tg.showAlert('Введите корректный username получателя');
        return;
    }
    
    const userId = tg.initDataUnsafe?.user?.id;
    const promo = document.getElementById('promo').value;
    
    if (!userId) {
        tg.showAlert('Не удалось определить пользователя');
        return;
    }
    
    let stars = 0;
    let months = 0;
    
    if (productType === 'stars') {
        stars = parseInt(document.getElementById('stars').value);
        if (stars < 50 || stars > 4999) {
            tg.showAlert('Количество звезд должно быть от 50 до 4999');
            return;
        }
    } else {
        months = selectedMonths;
    }
    
    const buyBtn = document.querySelector('.buy-btn');
    const originalHTML = buyBtn.innerHTML;
    buyBtn.disabled = true;
    buyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Создание заказа...';
    
    fetch('/create-order', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            user_id: userId,
            product_type: productType,
            stars: stars,
            months: months,
            promo_code: promo,
            payment_method: paymentMethod,
            recipient: recipientData.recipient
        })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => {
                throw new Error(err.detail || 'Ошибка создания заказа');
            });
        }
        return res.json();
    })
    .then(data => {
        if (data.payment_url) {
            window.location.href = data.payment_url;
        } else {
            throw new Error('Не получен URL оплаты');
        }
    })
    .catch(err => {
        tg.showAlert(err.message || 'Ошибка создания заказа');
        console.error(err);
        buyBtn.disabled = false;
        buyBtn.innerHTML = originalHTML;
    });
}

document.getElementById('stars').addEventListener('input', updatePrice);
document.getElementById('stars').addEventListener('blur', (e) => {
    const val = parseInt(e.target.value) || 50;
    e.target.value = Math.max(50, Math.min(4999, val));
    updatePrice();
});
