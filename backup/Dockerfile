FROM alpine:3.20
RUN apk add --no-cache postgresql15-client tzdata bash coreutils findutils
WORKDIR /backup
COPY backup.sh .
COPY crontab /etc/crontabs/root
RUN chmod +x /backup/backup.sh     # <— добавили
ENV TZ=Europe/Moscow
ENV PGHOST=db-primary PGPORT=5432 PGUSER=postgres PGPASSWORD=postgres
ENV BACKUP_DIR=/backups
ENV PGDATABASE=trading
ENV RETAIN=24
CMD ["sh","-lc","crond -f -l 8"]
