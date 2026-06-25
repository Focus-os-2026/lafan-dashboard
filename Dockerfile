FROM nginx:1.27-alpine

COPY lafan.dashboard.html /usr/share/nginx/html/lafan.dashboard.html
COPY ["Key visual_no artist.jpg", "/usr/share/nginx/html/Key visual_no artist.jpg"]
COPY pic/ /usr/share/nginx/html/pic/
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
