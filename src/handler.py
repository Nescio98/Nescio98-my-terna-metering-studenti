import sys
from shared import logger
from application import main


def run_task(event, context):
    # Scommentare il codice per abilitare la genereazione allo start, alla fine ed in caso di errore
    # try:
    #     publish_event("start", logger)
    try:
        logger.debug(
            "Starting program with arguments {}, event {}, context {}".format(
                sys.argv, event, context
            )
        )
        main()
    except:
        logger.error("An error occurred during execution", exc_info=True)
        exit(1)
        #     publish_event("fail", logger)
    finally:
        logger.debug("Program terminated.")
        # publish_event("success", logger)


if __name__ == "__main__":
    run_task(None, None)
