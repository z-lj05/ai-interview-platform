from app.core.celery_app import celery_app

if __name__ == '__main__':
    # 开发机上直接起 worker 用这个入口
    # Windows 上必须 --pool=solo：默认的 prefork 池依赖 fork，Windows 没有 fork
    # argv 不带 'celery' 前缀 —— start() 会把列表直接喂给 click 解析子命令，多一个前缀会报未知命令
    celery_app.start(['worker', '--loglevel=info', '--pool=solo'])
