/* 应用壳缓存：静态资源网络优先、失败回退缓存；API 不缓存 */
var CACHE_NAME = 'todo-shell-v2';
var SHELL = [
    '/login',
    '/static/theme.css',
    '/static/theme.js',
    '/static/icon.svg',
    '/static/icon-192.png',
    '/static/icon-512.png',
    '/static/manifest.json'
];

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches
            .open(CACHE_NAME)
            .then(function (cache) {
                return cache.addAll(SHELL);
            })
            .then(function () {
                return self.skipWaiting();
            })
    );
});

self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches
            .keys()
            .then(function (keys) {
                return Promise.all(
                    keys
                        .filter(function (key) {
                            return key !== CACHE_NAME;
                        })
                        .map(function (key) {
                            return caches.delete(key);
                        })
                );
            })
            .then(function () {
                return self.clients.claim();
            })
    );
});

self.addEventListener('fetch', function (event) {
    var url = new URL(event.request.url);

    if (
        event.request.method !== 'GET' ||
        url.origin !== self.location.origin ||
        url.pathname.indexOf('/api/') === 0
    ) {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(function (response) {
                var copy = response.clone();
                caches
                    .open(CACHE_NAME)
                    .then(function (cache) {
                        return cache.put(event.request, copy);
                    })
                    .catch(function () {});
                return response;
            })
            .catch(function () {
                return caches.match(event.request).then(function (cached) {
                    return cached || caches.match('/login');
                });
            })
    );
});
