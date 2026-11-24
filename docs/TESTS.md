# Tests

This document describes what a test of this project should be like, independently of the language or the framework. A test costs time each time it runs, it has to be read and it breaks when the code changes. For that reason a test that cannot catch a bug, or that fails without a bug, gives nothing back and teaches people to ignore a red result. The reasoning and the first suite are recorded in the decision "Tests only for a named behaviour" of `DECISIONS.md`.

## What a test protects

A test is written only when the behaviour it protects can be named from how a caller uses the code. For example, "a transfer larger than the balance is refused" is a behaviour, while "the function calls the helper twice" is an implementation detail. If the behaviour cannot be named, the test is probably noise and should not be written.

Six questions decide whether a test is kept. A test that fails one of the first four should be rewritten or deleted.

1. Which promised behaviour does it protect?
2. Would it fail if that behaviour broke? Someone should have seen it fail.
3. Would it keep passing after a refactor that changes nothing visible?
4. Does it give information that no other test gives?
5. Do its name and its message say what broke?
6. Is it fast and does it give the same result each time?

## How cases are chosen

The cases come from what the code promises and not from its branches. A function with ten branches may need three tests, and a function with one branch may need five. The usual techniques are the following.

* **Equivalence partitioning.** The inputs are divided into classes that the code treats in the same way, and one example of each class is enough. A second example of the same class adds no information.
* **Boundary value analysis.** For each ordered class, the test uses the edge value and the value beside it, because most mistakes happen there. For a range from 0.01 to 100.00 these are 0.00, 0.01, 100.00 and 100.01.
* **Decision tables.** When several conditions combine, one test covers each distinct outcome.
* **State transitions.** When behaviour depends on a state, one test covers each transition that matters, such as a pending account that becomes active.
* **Error guessing.** Experience says which inputs break this kind of code, such as an empty value, a very large number, a negative number, text where a number is expected or two requests at the same time. These are added by judgment.
* **Properties.** A rule that holds for any input, such as "the total money does not change after a transfer", can be tested with generated inputs. The generator needs a seed, and the seed is printed when the test fails so the failure can be reproduced.

## How a test is written

* The test has three parts in this order, which are the preparation, the action and the check.
* A test checks one behaviour, and its name reads as a sentence that says what is expected, for example `refuses_an_amount_with_three_decimals`.
* The check uses results and public state. It does not read private fields or depend on the order of internal calls, because such a test breaks when the code is reorganised without changing what it does.
* The test is a straight line. It has no loop, no condition and no expected value computed with a formula, because a test with logic needs its own test.
* The expected value is worked out by hand from the rule and is not produced with the same formula that the code uses, since both would be wrong together.
* Clarity matters more than brevity. A little repetition between tests is acceptable when it makes each one easy to read.
* Real objects are preferred over doubles. A double is used only when the real thing is slow, random or outside the program, such as a clock, the network or an external service. A double can agree with a wrong idea of the real component, so the behaviour that depends on it also needs a check against the real component.
* A failure message says what was expected, what happened and with which values.
* A test does not depend on the clock, on a random value without a seed, on the order of the tests or on the data left by another test.

## Kinds of test in this project

* **Unit tests** check one piece of logic without the database or the network. They are fast and run often. The validation of an amount, the password helpers and the transaction helper are examples.
* **Concurrency and integration checks** use the real stack, because behaviour such as row locks, unique keys and deadlocks exists only in the real database. They send many simultaneous requests and then check invariants, for example that no balance is negative, that each balance equals the sum of its ledger rows and that a transfer keeps the total money.
* **Security checks** are written as tests when a weakness is corrected, so the same request that used to work is sent again and the test shows that it is now refused. A failed login for an unknown email, a request for the account of another user and a request with an altered role are examples.

The commands that run each kind are in `CONTRIBUTING.md`.

## What does not deserve a test

| Test | Why it is noise |
|---|---|
| No check, or a check that cannot fail | It catches nothing and gives false comfort |
| Expected value computed with the formula of the code | Both are wrong together |
| A check on a private field or on the order of internal calls | It breaks after a refactor that changes nothing visible |
| A test of the framework or of a library | It can only fail because of code the project does not own |
| A test of a constant or of a getter with no rule behind it | The chance of a regression is almost zero and the upkeep is real |
| The tenth example of a class already covered | It adds no information |
| One test that checks several behaviours | A failure does not say what broke, and the first failed check hides the rest |
| A test with a condition that decides whether it checks | In some runs it checks nothing |
| A test written only to raise the coverage number | It runs code without verifying it |
| A disabled test left in the project | Nobody reads it |

## Checking a test

A test counts only after it was seen failing. When a test or a fix is added, the code it protects is broken on purpose, for example by changing a comparison or removing a line, and the test has to fail. Then the code is restored. Mutation testing tools automate this idea, and they were not used in this project, so the check is done by hand and depends on attention.

## Coverage

A coverage number can show code that no test runs, but it cannot show whether the tests verify anything. It is used to look for gaps and is not a target, because a target pushes people to write tests that execute code without checking it.

## Sources

The rules above come from the testing guide of the documentation system skill used in this project, which was read in full. That guide cites the ISTQB definitions of equivalence partitioning and boundary value analysis, ISO/IEC/IEEE 29119-4, the chapter on unit testing of Software Engineering at Google, the Test Desiderata of Kent Beck and the article on test coverage of Martin Fowler. None of those sources was read for this document, so the wording is the guide's summary and not a quotation. The rule that the framework is not tested is a judgment of the guide and no source states it.
