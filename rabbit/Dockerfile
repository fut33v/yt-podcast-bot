FROM rabbitmq:management-alpine

ENV RABBITMQ_USER user
ENV RABBITMQ_PASSWORD password

COPY rabbitmq.conf /etc/rabbitmq/
COPY definitions.json /etc/rabbitmq/

ADD init.sh /init.sh

EXPOSE 5672
EXPOSE 15672

CMD ["/init.sh"]
