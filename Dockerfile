FROM python:3.10.8-slim
RUN apt-get update
RUN apt-get install -y locales
RUN sed -i '/pt_BR/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG pt_BR
ENV LANGUAGE pt_BR 
ENV LC_ALL pt_BR

RUN mkdir -p /app

COPY ./app /app
COPY ./requirements.txt /app/requirements.txt

WORKDIR /app

RUN python -m pip install -r requirements.txt

EXPOSE 8000

CMD ["python", "main.py"]