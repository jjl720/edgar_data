FROM public.ecr.aws/lambda/python:3.9
COPY main.py /var/task
COPY secApi_extractor.py /var/task
COPY config.py /var/task
COPY .env /var/task
COPY requirements.txt /var/task
RUN yum -y install git
RUN pip install -r requirements.txt
RUN pip install git+https://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@github.com/cultureline-ai/clai_utils.git