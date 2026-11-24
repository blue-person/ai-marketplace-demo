# Decisions

This document records the important technical decisions of the project, one entry for each. Every entry says what was decided, why, which options were discarded and which sources support the choice, so the reasoning can be checked later. New entries are added at the end and old ones are not rewritten. When a decision changes, a new entry is added and the old one is marked as replaced.

## Index

| Number | Decision | Status | Date |
|---|---|---|---|
| 1 | Use parameterized SQL queries | Accepted, partly applied | 2026-11-23 |
| 2 | Store passwords with Argon2id | Accepted and applied | 2026-11-23 |
| 3 | Answer every failed login in the same way | Accepted and applied | 2026-11-23 |
| 4 | Require at least 15 characters in passwords | Accepted and applied | 2026-11-23 |

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

The login still compares the password hash inside the SQL statement, which will change when the password storage is replaced. The route that updates an account builds column names from the request, and placeholders cannot protect names, so it will need a fixed list of editable fields together with the access control work. The exact quotes of the OWASP pages have to be copied from the live pages before the final reports.

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
