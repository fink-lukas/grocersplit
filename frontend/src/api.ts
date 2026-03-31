import axios from 'axios';

const api = axios.create({
    baseURL: '/api',
    withCredentials: true,
});

let isRefreshing = false;
let refreshSubscribers: (() => void)[] = [];

const onRefreshed = () => {
    refreshSubscribers.forEach((cb) => cb());
};

const addRefreshSubscriber = (cb: () => void) => {
    refreshSubscribers.push(cb);
};

api.interceptors.response.use(
    (response) => {
        return response;
    },
    async (error) => {
        const originalRequest = error.config;
        
        if (error.response?.status === 401 && !originalRequest._retry) {
            
            if (isRefreshing) {
                return new Promise((resolve) => {
                    addRefreshSubscriber(() => {
                        originalRequest._retry = true;
                        resolve(api(originalRequest));
                    });
                });
            }

            originalRequest._retry = true;
            isRefreshing = true;
            
            try {
                await axios.post('/auth/refresh', {}, {
                    baseURL: '/api',
                    withCredentials: true
                });
                isRefreshing = false;
                onRefreshed();
                refreshSubscribers = [];
                return api(originalRequest);
            } catch (refreshError) {
                isRefreshing = false;
                refreshSubscribers = [];
                return Promise.reject(refreshError);
            }
        }
        return Promise.reject(error);
    }
);

export default api;
