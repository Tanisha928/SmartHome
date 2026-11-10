# SQS inference-events + DLQ stub.

# resource "aws_sqs_queue" "inference_dlq" {
#   name = "inference-events-dlq"
# }
#
# resource "aws_sqs_queue" "inference_events" {
#   name                       = "inference-events"
#   visibility_timeout_seconds = 120
#   receive_wait_time_seconds  = 20
#   redrive_policy = jsonencode({
#     deadLetterTargetArn = aws_sqs_queue.inference_dlq.arn
#     maxReceiveCount     = 3
#   })
# }
