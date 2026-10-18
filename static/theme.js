/* 主题切换、PWA 注册与全局无障碍小部件 */
(function () {
    var STORAGE_KEY = 'todo-theme';
    var root = document.documentElement;
    var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    var stored = null;

    try {
        stored = localStorage.getItem(STORAGE_KEY);
    } catch (error) {
        stored = null;
    }

    var initial = stored || (media && media.matches ? 'dark' : 'light');
    if (initial === 'dark') {
        root.classList.add('dark');
    }

    function updateButton(button) {
        var dark = root.classList.contains('dark');
        button.textContent = dark ? '☀️' : '🌙';
        button.setAttribute('aria-label', dark ? '切换到浅色模式' : '切换到深色模式');
        button.title = dark ? '切换到浅色模式' : '切换到深色模式';
    }

    document.addEventListener('DOMContentLoaded', function () {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'theme-toggle';
        document.body.appendChild(button);
        updateButton(button);

        button.addEventListener('click', function () {
            var dark = !root.classList.contains('dark');
            root.classList.toggle('dark', dark);
            try {
                localStorage.setItem(STORAGE_KEY, dark ? 'dark' : 'light');
            } catch (error) {
                // 隐私模式下 localStorage 可能不可用
            }
            updateButton(button);
        });

        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js').catch(function () {
                // PWA 注册失败不影响页面使用
            });
        }
    });
})();
