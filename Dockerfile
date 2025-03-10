FROM python:3.13.2-alpine3.21

WORKDIR /app
COPY . .

EXPOSE 8080

RUN pip install nb-cli

RUN pip install nonebot[fastapi]

RUN pip install -r requirements.txt

CMD ["nb", "run", "--reload"]