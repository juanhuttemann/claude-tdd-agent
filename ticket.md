# Feature: Add email to User with validations and search

## Background
Users currently only have a `name` field. We need to add an `email` field and enforce data integrity.

## Requirements

### 1. Migration
- Add a `email` column (string, not null) to the `users` table.
- Add a unique database index on `email`.

### 2. Model validations
- `name` must be present and at most 100 characters.
- `email` must be present, unique (case-insensitive), and match a basic email format (`something@something.something`).
- `email` should be normalized to lowercase before saving.

### 3. Controller changes
- Permit the `email` parameter in strong params.
- Add a `GET /users/search?q=<query>` action that returns users whose name **or** email contains the query string (case-insensitive). Respond with JSON array of matching users (`id`, `name`, `email`). Return an empty array if `q` is blank.

### 4. Route
- Add the search route as a collection route on users: `GET /users/search`.
