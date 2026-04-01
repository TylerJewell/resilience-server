package com.example.domain;

public record Greeting(String name) {

  public Greeting withName(String name) {
    return new Greeting(name);
  }
}
