mock_provider "databricks" {}

run "alpha" {
  command = plan
  variables {
    stack = jsondecode(file("../stacks/alpha.tfvars.json")).stack
  }

  assert {
    condition     = output.bundle_vars.gold_schema == "slh_alpha_dev_gold"
    error_message = "Alpha's Gold schema must include its team and environment."
  }
}

run "bravo" {
  command = plan
  variables {
    stack = jsondecode(file("../stacks/bravo.tfvars.json")).stack
  }

  assert {
    condition     = output.bundle_vars.gold_schema == "slh_bravo_prod_gold"
    error_message = "Bravo's Gold schema must include its team and environment."
  }
}

run "reject_disposable_prod" {
  command = plan
  variables {
    stack = merge(jsondecode(file("../stacks/bravo.tfvars.json")).stack, { disposable = true })
  }

  expect_failures = [var.stack]
}
