terraform {
  backend "gcs" {
    bucket = "slh-gcp-test-tfstate"
    prefix = "g06/stacks/alpha"
  }
}
