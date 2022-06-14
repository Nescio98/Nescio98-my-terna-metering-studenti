# #import serverless requirements packages
# try:
#     import unzip_requirements
# except ImportError:
#     pass


from .application import application as app


# AWS Lambda handler
# from application.builder import LambdaConfiguration as Config
# def handler(event, context):
#     configuration = Config(event, context).build()
#     App.factory(configuration).run()


# Docker entrypoint
from application.builder import AppConfiguration as Config
if __name__ == "__main__":
    configuration = Config().build()
    app.factory(configuration).run()
