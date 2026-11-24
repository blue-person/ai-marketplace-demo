# Decisions

This document records the important technical decisions of the project, one entry for each. Every entry says what was decided, why, which options were discarded and which sources support the choice, so the reasoning can be checked later. New entries are added at the end and old ones are not rewritten. When a decision changes, a new entry is added and the old one is marked as replaced.

## Index

| Number | Decision | Status | Date |
|---|---|---|---|
| 1 | Use parameterized SQL queries | Accepted, partly applied | 2026-11-23 |
| 2 | Store passwords with Argon2id | Accepted and applied | 2026-11-23 |
| 3 | Answer every failed login in the same way | Accepted and applied | 2026-11-23 |
| 4 | Require at least 15 characters in passwords | Accepted and applied | 2026-11-23 |
| 5 | Handle every SQL operation that writes data under ACID | Accepted, not applied yet | 2026-11-23 |
| 6 | Use mysql-connector-python with a transaction helper and tenacity | Accepted and applied | 2026-11-23 |
| 7 | Apply the transaction helper, the retry rule and the credit transfers | Accepted and applied | 2026-11-24 |

## 1. Use parameterized SQL queries

Decided on 2026-11-23. The status is accepted, and it is applied to the login and to the directory search.

### Context

The starter template built some SQL statements by joining text with string formatting. Anything a user typed in those places became part of the query, so it could change what the query meant.

### Decision

Every query sends the values of the user as parameters through `%s` placeholders, and no query builds its text by joining or formatting strings with request data.

### Reasons

OWASP lists prepared statements with parameterized queries as its first defense against SQL injection, because the structure of the query is fixed before any value arrives. The driver used by the backend, `mysql-connector-python` 26.10.0, accepts `%s` placeholders in `execute()`, and its default cursor substitutes the values with escaping applied. This was checked in the source code of the installed version. The change is also small and easy to read, which helps the reviewers.

After the change, the same requests that had altered the queries were sent again to the local copy and no longer worked. A normal login, a wrong password and searches with and without quotes still gave the expected results.

### Alternatives discarded

* Escaping quotes by hand, which OWASP keeps as a last resort because it is easy to miss a case.
* The prepared cursor of the connector, which was not needed because the default cursor already separates the values and it keeps the behavior the same as in the rest of the code.
* Stored procedures, which OWASP accepts as a secondary option but which would add database objects to maintain for a project of this size.

### References

* [SQL Injection Prevention Cheat Sheet, OWASP](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
* [Query Parameterization Cheat Sheet, OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html)
* [MySQL Connector/Python, cursor.execute()](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-execute.html)

### Where it applies

The change is in `backend/app/routes_auth.py` for the login and in `backend/app/routes_general.py` for the directory.

### Open points

The login no longer compares the password hash inside the SQL statement, because decision 2 moved the check to Python. The route that updates an account builds column names from the request, and placeholders cannot protect names, so it will need a fixed list of editable fields together with the access control work. The exact quotes of the OWASP pages have to be copied from the live pages before the final reports.

## 2. Store passwords with Argon2id

Decided on 2026-11-23. The status is accepted, and it is applied to the sign up, the login and the seed.

### Context

The starter template stores passwords as MD5 hashes with no salt. Two accounts with the same password therefore get the same hash, which was seen in the test accounts. MD5 is also very fast to compute, so an attacker who copies the database can test a huge number of guesses every second.

### Decision

Passwords will be stored with Argon2id, using 19 MiB of memory, 2 iterations and a parallelism of 1. A maintained library (`argon2-cffi`) will do the work, and no hashing code will be written by hand. The settings will be measured on the machine that runs the application, and they will be lowered to 12 MiB and 3 iterations if one hash takes too long.

### Reasons

OWASP puts Argon2id first among the algorithms for storing passwords. It lists several configurations that give the same level of defense and only trade memory for iterations, and the chosen one is the minimum with the most common balance. Its guidance is that one hash should take less than one second, and that the right settings are found by testing on the real server.

The cost is small for this project. The backend runs 2 processes with 2 threads each, so at most 4 hashes happen at once, which is about 76 MiB at the peak and is released right after each check. Hashing only happens when someone signs up or signs in. There is also no requirement to use FIPS validated algorithms, which is the main reason to prefer another option. The library takes care of the salt, the stored format and the verification.

### Alternatives discarded

* scrypt, which OWASP places second and which comes with Python, but the salt and the stored format would have to be handled by hand, and its first configuration needs 128 MiB.
* bcrypt, which OWASP keeps for legacy systems where Argon2 and scrypt are not available. It also cuts the password at 72 bytes in most implementations, so that limit would need its own rule.
* PBKDF2, which OWASP recommends when FIPS-140 compliance is required. That requirement does not exist here.
* Keeping MD5, which is the weakness this decision removes.

### References

* [Password Storage Cheat Sheet, OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

### Where it applies

The sign up and the login in `backend/app/routes_auth.py`, the accounts created by `backend/app/seed.py`, the new module `backend/app/passwords.py` and a new dependency (`argon2-cffi`) in the `backend` project. The test database was recreated with `docker compose down -v`, so no MD5 hash had to be migrated.

### Open points

The cost was measured inside the backend container of the development machine, which has 2 processors and about 1.9 GB of memory. Creating one hash took about 36 ms and checking one took between 33 and 40 ms, so the plan to lower the settings was not needed. The backend process stayed around 65 MiB. The five test accounts now have five different hashes, and each one starts with `$argon2id$v=19$m=19456,t=2,p=1$`. API keys are random values and not chosen passwords, so the way to store them will be decided in a separate entry with its own sources. A pepper, which is a secret shared by all accounts and kept outside the database, was considered and postponed. OWASP describes it as optional and as an extra layer of defense, it asks to keep it in a secrets vault or a hardware module, and it warns that changing it forces every user to reset the password. Its guidance also gives no recipe for combining a pepper with Argon2id. The idea can be reviewed again after the modules are built.

## 3. Answer every failed login in the same way

Decided on 2026-11-23. The status is accepted, and it is applied to the login.

### Context

The login answered with a 403 and the account status when the password was right but the account was not active, and with a 401 and a generic message in every other failure. That difference told an attacker that the password was correct, even though the login was refused.

### Decision

Every failed login now gets the same 401 and the same message, whether the email does not exist, the password is wrong or the account is not active. A password check always runs, and when the account does not exist the typed password is checked against a stored dummy hash, so the answer takes a similar time in all cases. A good login returns only the id, the name, the email and the role, and never the hash.

### Reasons

The OWASP Authentication Cheat Sheet asks for a generic message whether the user ID or the password was wrong, the account does not exist, or the account is locked or disabled. It lists "account disabled" among the messages to avoid. It also warns that different response codes for success and failure can reveal whether an account is valid, and it recommends running the same steps in every case so the response time is similar.

After the change, a wrong password, a missing email and a pending account with the right password all returned the same 401 and the same message. The mean time of eight requests was 0.093 s for a missing email, 0.086 s for a wrong password and 0.088 s for a good login, so the differences are a few milliseconds and include the overhead of the request.

### Alternatives discarded

* Keeping the 403 with the account status, which is more convenient for the user but tells an attacker that the password is right.
* Keeping different messages and relying only on a limit of attempts, because that limit does not exist yet and OWASP asks for both measures.

### References

* [Authentication Cheat Sheet, OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

### Where it applies

The login in `backend/app/routes_auth.py` and the helpers in `backend/app/passwords.py`.

### Open points

A person with a pending account now sees the same error as anyone else and learns about the pending state only from the message shown at sign up. The limit of failed attempts is still to be built. The sign up still answers that an email is already registered, which reveals the accounts that exist. The session is still a signed cookie that the server does not invalidate. The time comparison was not repeated with a statistical test.

## 4. Require at least 15 characters in passwords

Decided on 2026-11-23. The status is accepted, and it is applied to the sign up.

### Context

The starter template accepted any password of 6 characters or more.

### Decision

The sign up requires at least 15 characters, and no rule about uppercase letters, numbers or symbols is added.

### Reasons

The OWASP Authentication Cheat Sheet says the application must enforce a minimum length, and that passwords shorter than 8 characters are weak with a second factor and shorter than 15 characters are weak without one. This application has no second factor. The same page asks for no composition rules, for accepting all characters including spaces and unicode, for not truncating passwords silently and for a maximum length of at least 64 characters.

A password of 8 characters was refused with a 400 and a clear message, and a password of 19 characters was accepted.

### Alternatives discarded

* A minimum of 8 characters, which OWASP accepts only when there is a second factor.
* Composition rules such as required symbols, which the same page advises against.

### References

* [Authentication Cheat Sheet, OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

### Where it applies

The constant `MIN_PASSWORD_LENGTH` in `backend/app/passwords.py` and the sign up in `backend/app/routes_auth.py`.

### Open points

No maximum length is set yet, and passwords that are common or that appeared in leaks are not blocked, which OWASP also recommends. The sign up form does not show the minimum before sending, because the answer of the backend is the source of truth.

## 5. Handle every SQL operation that writes data under ACID

Decided on 2026-11-23. The status is accepted, and it is not applied yet because most modules are still to be built and the current sign up and login have to be reviewed against it.

### Context

The application writes to the database in many places. These are the sign up, the approval of accounts, the generation of API keys, the publication and approval of agents, the charge of an agent execution, the scheduled executions that the robot launches, the transfers between users and the referral bonus. Several requests can touch the same rows at the same time, some operations need more than one statement, and some call an external service in the middle. Without clear rules, a repeated sign up or a double approval could pass a check twice, or an operation could stop halfway and leave the data inconsistent. Money is where an error costs most, but the same risks apply to any other data.

### Decision

Every operation that writes to the database, or that needs a consistent view across several statements, follows ACID, which means atomicity, consistency, isolation and durability. The rules apply to every table.

* Each business operation runs in one transaction that is opened and closed in one place, with a commit when everything works and a rollback on any error. A small helper in `db.py` will provide it, so no module repeats that logic.
* The check and the change happen together, either in one conditional statement or under a row lock taken with `SELECT ... FOR UPDATE`. For example, `UPDATE accounts SET status = 'active' WHERE id = x AND status = 'pending'` approves an account only once, and `UPDATE accounts SET balance = balance - cost WHERE id = x AND balance >= cost` charges only when the balance is enough. A plain read followed by a separate write is not used.
* The database also enforces the rules. Tables use InnoDB, and they declare unique keys, foreign keys, required columns, `CHECK` constraints and exact numeric types where they apply. A duplicate that slips through the code, such as two sign ups with the same email at the same time, is stopped by the unique key, and the code turns that error into a clean answer.
* No call to an external service happens inside an open transaction, and emails are sent after the commit. When an operation needs the result of a call, a short transaction saves the change in the state `pending`, the call is made, and a second short transaction saves the result. When the call fails, the change is undone with a compensating action.
* To avoid deadlocks, transactions are kept short and the rows are always touched in the same order, for example the account with the lower id first. When MySQL reports a deadlock, the whole transaction is retried a limited number of times.
* Operations that can be repeated, such as a robot launch or a repeated request, carry a key that is unique in the database, so a repetition cannot apply the same change twice.
* Money adds one rule. Every change of a balance also writes a row in an append-only ledger, in the same transaction, and a mistake is corrected with a new reversing row and never by editing a row. Balances have a `CHECK` that forbids negative values and use an exact numeric type.
* Tests send many requests at the same time. They check that no balance is negative, that each balance equals the sum of its ledger rows, that a transfer keeps the total amount of money, that two sign ups with the same email create one account, and that approving the same account twice pays the referral bonus once.

### Reasons

The MySQL manual says that InnoDB uses REPEATABLE READ by default, and that a plain `SELECT` reads a snapshot taken by the first read of the transaction. A check made on that snapshot does not protect a later write, so two requests can both see the same state. This applies to a balance, to the status of an account and to the existence of an email in the same way. Locking reads and writes use the latest committed data, and the manual advises against mixing both kinds of reads in one transaction.

The manual also says that deadlocks are not dangerous in themselves and that an application has to be ready to run a rolled back transaction again, and it suggests short transactions and a consistent order when touching rows. The documentation of Connector/Python confirms that autocommit is off by default, that `commit()` must be called after every transaction that changes data, and that `rollback()` undoes it, which is what the `db.py` helper will wrap. Constraints of type `CHECK` are enforced since MySQL 8.0.16, so the database can refuse a negative balance by itself.

The practice of an append-only ledger with reversing entries and a unique key for repeated operations comes from articles about payment systems, which are not a standard and are used only as guidance.

### Alternatives discarded

* Applying ACID only to the operations with money, because a repeated sign up or a double approval breaks the data in the same way.
* Reading a value with a plain `SELECT` and writing it later, because two requests can both pass the check.
* Keeping a transaction open while the AI service answers, because the rows stay locked for all that time and the slow simulated model takes five seconds.
* Storing money in an approximate numeric type such as `FLOAT`, which can lose fractions.
* Editing or deleting ledger rows, because the history could no longer be trusted.

### References

* [InnoDB Transaction Isolation Levels, MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html)
* [Consistent Nonlocking Reads, MySQL 8.4](https://docs.oracle.com/cd/E17952_01/mysql-8.4-en/innodb-consistent-read.html)
* [How to Minimize and Handle Deadlocks, MySQL 8.4](https://docs.oracle.com/cd/E17952_01/mysql-8.4-en/innodb-deadlocks-handling.html)
* [CHECK constraints, MySQL 8.0](https://dev.mysql.com/doc/refman/8.0/en/create-table-check-constraints.html)
* [start_transaction(), Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-start-transaction.html)
* [commit(), Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-commit.html)
* [Transactions and Connection Management, SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
* [Design a payment ledger, article on DEV Community](https://dev.to/gabrielanhaia/design-a-payment-ledger-idempotent-audit-compliant-reconciles-to-the-cent-59p7)

### Where it applies

The helper in `backend/app/db.py` and every module that writes data. These are the sign up, the rehash done at login, the update of accounts, the approval of accounts, the API keys, the catalog, the execution of agents, the scheduled executions and their robot, the transfers, the referral bonus and the seed.

### Open points

These sources were read through search results and not as complete pages, so the exact wording has to be checked in the manual before the report, especially the section about the locks that InnoDB sets for each statement. Three questions remain open. The first is how `cursor.rowcount` behaves with Connector/Python after an `UPDATE`, which the search did not answer and which must be tested because the conditional update depends on it. The second is the official page about exact numeric types, which confirms why money uses `DECIMAL`. The third is the choice between a small helper over Connector/Python and a library such as SQLAlchemy, whose `sessionmaker.begin()` and `with_for_update()` already cover transactions and row locks. The retry library and the rules of PEP 249 about autocommit were not researched. The scale of the money columns, the number of retries and the exact design of the keys for repeated operations are still to be decided. The current sign up checks the email with a `SELECT` before the `INSERT`, so it must be reviewed against these rules.

## 6. Use mysql-connector-python with a transaction helper and tenacity

Decided on 2026-11-23. The status is accepted, and it is not applied yet.

### Context

Decision 5 asks that every operation that writes data follows ACID, and that a transaction is repeated when MySQL reports a deadlock. The project already reads and writes through `mysql-connector-python` with SQL written by hand and a small `db.py`. A choice was needed between keeping that base and adding a library for transactions.

### Decision

The access to the database stays with `mysql-connector-python`, and the SQL stays written by hand. A helper named `transaction()` is added to `db.py` as a `with` block built on the `commit()` and `rollback()` methods of the connector. The library `tenacity` repeats the whole operation, with a limited number of attempts and a waiting time, when MySQL reports a deadlock.

### Reasons

The connector is already part of the project and its documentation lists `start_transaction()`, `commit()` and `rollback()`, so the helper is a small pattern over documented functions and not a new tool. Writing the SQL by hand keeps statements such as a conditional `UPDATE` fully visible, which makes them easy to review and to explain. No existing code has to be rewritten.

The MySQL manual says that an application must be ready to run a rolled back transaction again after a deadlock. `tenacity` is a general-purpose retry library for Python, and its documentation splits the behavior in modules for the condition to retry, the waiting time and the stop rule. A deadlock can be recognized by the error number 1213 in the exception of the connector, and the documentation of Connector/Python says that its internal error class is raised, for example, when a deadlock occurred.

### Alternatives discarded

* SQLAlchemy, which already offers `sessionmaker.begin()` and `with_for_update()`, but it would require rewriting all the data access. Its object mode also hides the SQL that has to be reviewed, and its main benefit, changing the database engine, is not needed here.
* A retry decorator written for this project, which works but is code written by the team for something that a library already does.
* No retries, because the manual says deadlocks are expected and have to be handled.

### References

* [start_transaction(), Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-start-transaction.html)
* [commit(), Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-commit.html)
* [InternalError, Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-api-errors-internalerror.html)
* [How to Minimize and Handle Deadlocks, MySQL 8.4](https://docs.oracle.com/cd/E17952_01/mysql-8.4-en/innodb-deadlocks-handling.html)
* [Documentation of tenacity](https://tenacity.readthedocs.io/)
* [Transactions and Connection Management, SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)

### Where it applies

`backend/app/db.py` for the helper, the new dependency in the `backend` project, and every module that writes data.

### Open points

The documentation of `tenacity` was reached only through search results, which describe its modules but not the details. Before using it, its pages have to be read to confirm the names of the conditions, the stop rule and the waiting time that will be used. By default it raises its own error when the attempts end, so the option that returns the original error has to be confirmed. It also has to be confirmed which exception class carries the error number 1213 and whether the error 1205, which is a lock wait that took too long, should be repeated as well, since the sources treat it as less clear. The number of attempts and the waiting time are still to be decided. The repetition must wrap the whole operation including its reads, and an operation that calls an external service must not be repeated blindly, which is why decision 5 asks for a key that is unique in the database.

## 7. Apply the transaction helper, the retry rule and the credit transfers

Decided on 2026-11-24. The status is accepted and applied. It carries out decisions 5 and 6 for the code that exists today and for the transfers module.

### Context

Decisions 5 and 6 set the rules but no code followed them yet. The sign up checked the email with a `SELECT` before the `INSERT`, so two sign ups with the same email at the same time ended in a 500 with a stack trace. The route that updates an account accepted any column, so a balance column would have been editable by any user. The analysis is in `.sandbox/acid-analysis.md`.

### Decision

* `db.py` opens the connection with autocommit enabled, so a plain read sees the last committed data. Every write goes through `transaction()`, which calls `start_transaction()`, then `commit()` at the end of the block or `rollback()` on any error. The old `execute()` and `commit()` functions were removed, so there is no way to write outside a transaction.
* Inside the block, `execute()` returns the number of rows the statement changed, and `insert()` returns the new id. A broken unique key (error 1062) becomes `DuplicateError`, a neutral name, and no other file imports the connector errors.
* `retry_on_deadlock` repeats the whole decorated function only when the error number is 1213. It uses `tenacity` with 3 attempts, a random exponential wait of at most 0.5 s and `reraise=True`. The error 1205 is not repeated, and `innodb_lock_wait_timeout` is not changed.
* The sign up has no `SELECT` before the `INSERT` and answers 409 when the unique key stops a repeated email. The rehash at login uses the same helper.
* `GET /api/accounts/<id>` returns only the public columns and only to the owner or an administrator. `PUT` changes only the name and only of the own account.
* The unexpected error handler answers a generic 500 and keeps the details in the log.
* Money uses `DECIMAL(12,2)`. A table `transfers` and an append-only table `ledger_entries` were added, and `accounts.balance` has a `CHECK` against negative values. The seed gives 100.00 USD to each new account that is not an administrator, through a `seed_credit` ledger row in the same transaction.
* A transfer locks both accounts in the order of their ids with `SELECT ... FOR UPDATE`, charges the sender with `UPDATE ... WHERE balance >= amount`, credits the recipient and writes the transfer with its two ledger rows, all in one transaction. The routes are in `routes_credit.py` and the page is `CreditView.vue`.

### Reasons

The MySQL manual says that an application must be ready to run a transaction again after a deadlock, that InnoDB rolls back the whole transaction in that case, and that a consistent order when touching rows lets transactions form queues without deadlocks. It also says that a lock wait timeout rolls back only the statement and that `innodb_rollback_on_timeout` is off by default, which is why only the error 1213 is repeated. The `tenacity` documentation says that without a stop rule and a wait it retries forever without waiting, that `reraise=True` raises the original error instead of `RetryError`, and that `wait_random_exponential` is meant for several processes that compete for the same resource.

The pages of Connector/Python say that `rowcount` works like `mysql_affected_rows()`, and the MySQL manual says that for an `UPDATE` this value is by default the number of rows actually changed. The connection of the backend does not set `CLIENT_FOUND_ROWS`, which was checked in the running container. For that reason every conditional `UPDATE` changes a value for sure, because the amounts are always greater than zero, and a count of 0 means that the condition failed. The manual also says that an insert with too many decimals is rounded without an error even in strict mode, so the route validates the amount with `Decimal` before sending it.

Tests that ran against the real stack after a rebuild with `docker compose down -v`. Twenty sign ups with the same email at the same time created one account and returned 19 answers 409. Thirty transfers of 5.00 from an account with 100.00 gave 20 successes and 10 answers 402, and the balance ended at 0.00. Forty crossed transfers between two accounts all worked and the total money did not change. No balance was negative, every balance matched the sum of its ledger rows, and each transfer had exactly two ledger rows. The log of the backend had no unhandled error. A deadlock was also provoked on purpose with two transactions that lock two accounts in opposite order. One of them was rolled back by MySQL, was run again by `retry_on_deadlock` and finished on its second attempt.

### Alternatives discarded

* Keeping autocommit disabled, because the transaction would start at the first read of the request and not where the block starts.
* Repeating the error 1205, because only the statement is rolled back and the wait is a sign of a design problem more than of a normal collision.
* Using `SKIP LOCKED` or `SERIALIZABLE`, because the conditional `UPDATE` with row locks is enough and the manual warns that `SKIP LOCKED` gives an inconsistent view.
* Integers in cents, which are exact too, but they need a conversion at every input and output.

### References

* [How to Minimize and Handle Deadlocks, MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlocks-handling.html)
* [InnoDB Error Handling, MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/innodb-error-handling.html)
* [Locking Reads, MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html)
* [Locks Set by Different SQL Statements, MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html)
* [Rounding Behavior, MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/precision-math-rounding.html)
* [Fixed-Point Types, MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/fixed-point-types.html)
* [ROW_COUNT(), MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/information-functions.html)
* [cursor.rowcount, Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-rowcount.html)
* [start_transaction(), Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-start-transaction.html)
* [Documentation of tenacity](https://tenacity.readthedocs.io/en/latest/)

### Where it applies

`backend/app/db.py`, `routes_auth.py`, `routes_general.py`, `routes_credit.py`, `seed.py` and `__init__.py`, the file `database/init/02-credit.sql`, the page `frontend/src/views/CreditView.vue` and the test script `scripts/concurrency_check.py`. The dependency `tenacity` 9.2.1 was added to the `backend` project.

### Open points

The number of 3 attempts and the wait values are a choice of the team and no source gives them. The documentation of `tenacity` does not say whether it is safe with threads, and the deadlock test ran with two threads and worked, but it is not a proof. The exception class that the server raises for a `CHECK` violation was not tested, since the routes check the amounts before the database does. The script of concurrency tests expects a fresh database, because the overdraft test starts from an account with 100.00. Idempotency keys for repeated client requests were left out. The agent execution, the scheduled executions and the referral bonus are still to be built with the same helper, and they will need the three step flow for the external call. The OWASP WSTG page about usage limits could not be read, so it is not cited. A recipient is found by email, so the answer of a transfer tells whether an email exists, which is related to the open point about sign up enumeration.

## Template for a new entry

Copy the following block to the end of the document, give it the next number and add a row to the index.

```markdown
## N. Short title of the decision

Decided on YYYY-MM-DD. The status is accepted, proposed or replaced.

### Context

What was happening and why a decision was needed.

### Decision

What was chosen, in one or two sentences.

### Reasons

Why it was chosen, with the evidence found in the code or in the tests.

### Alternatives discarded

* Each option that was considered and the reason it was left out.

### References

* [Name of the source](https://example.com), only sources that were really read.

### Where it applies

The files, services or modules that change.

### Open points

What is still pending or not verified.
```
