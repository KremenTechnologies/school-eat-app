create table if not exists users (
  id          bigserial primary key,
  phone       text unique not null,
  full_name   text not null,
  role        text not null check (role in ('developer','admin','teacher')),
  class_name  text not null default '',
  created_at  timestamptz not null default now()
);

create table if not exists classes (
  name text primary key
);

create table if not exists settings (
  id        int primary key default 1 check (id = 1),
  bot_token text not null default '',
  chat_id   text not null default ''
);
insert into settings (id) values (1) on conflict do nothing;

create table if not exists attendance (
  date             date not null,
  class_name       text not null,
  registered       int  not null default 0,
  abroad           int  not null default 0,
  individual       int  not null default 0,
  illness_count    int  not null default 0,
  illness_names    text not null default '',
  grvi_count       int  not null default 0,
  grvi_names       text not null default '',
  family_count     int  not null default 0,
  family_names     text not null default '',
  no_reason_count  int  not null default 0,
  no_reason_names  text not null default '',
  breakfast        int,
  lunch            int,
  signature        text not null default '',
  updated_at       timestamptz not null default now(),
  updated_by       text not null default '',
  primary key (date, class_name)
);

create table if not exists login_codes (
  phone      text primary key,
  code       text not null,
  expires_at timestamptz not null,
  attempts   int not null default 0
);
