#!/bin/bash

################################################################
# SET THE ENVIRONMENT VARIABLES USED BY THE BITBUCKET PIPELINE #
################################################################

export AWS_DEFAULT_REGION=$(eval echo "$"${SERVICE}_${STAGE}_AWS_DEFAULT_REGION)
echo "Exported AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION"

export AWS_ACCOUNT_ID=$(eval echo "$"${SERVICE}_${STAGE}_AWS_ACCOUNT_ID)
echo "Exported AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID"

export AWS_ACCESS_KEY_ID=$(eval echo "$"${SERVICE}_${STAGE}_AWS_ACCESS_KEY_ID)
echo "Exported AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"

export AWS_SECRET_ACCESS_KEY=$(eval echo "$"${SERVICE}_${STAGE}_AWS_SECRET_ACCESS_KEY)
echo "Exported AWS_SECRET_ACCESS_KEY=****"