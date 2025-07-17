# 6 MB 極小映像，只做一次 curl
FROM alpine:3.20
RUN apk add --no-cache curl
CMD curl -s https://surebet-bot-pk05.onrender.com
