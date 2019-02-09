FROM mongo
RUN apt-get update
RUN apt-get install python3 python3-pymongo -y
COPY task_setup.py /
COPY task_setup.sh /
RUN chmod +x /task_setup.sh
CMD ["/task_setup.sh"]


