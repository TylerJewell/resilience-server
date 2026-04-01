package com.example.api;

import akka.javasdk.testkit.TestKit;
import akka.javasdk.testkit.TestKitSupport;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class GreetingEndpointIntegrationTest extends TestKitSupport {

  @Test
  void shouldReturnDefaultGreeting() {
    var response = httpClient.GET("/hello/test-1")
        .responseBodyAs(GreetingEndpoint.GreetingResponse.class)
        .invoke();

    assertThat(response.status().isSuccess()).isTrue();
    assertThat(response.body().message()).isEqualTo("Hello, World!");
    assertThat(response.body().nodePort()).isGreaterThan(0);
  }

  @Test
  void shouldSetAndGetGreeting() {
    var setResponse = httpClient.PUT("/hello/test-2")
        .withRequestBody(new GreetingEndpoint.SetNameRequest("Alice"))
        .invoke();
    assertThat(setResponse.status().isSuccess()).isTrue();

    var getResponse = httpClient.GET("/hello/test-2")
        .responseBodyAs(GreetingEndpoint.GreetingResponse.class)
        .invoke();
    assertThat(getResponse.body().message()).isEqualTo("Hello, Alice!");
    assertThat(getResponse.body().nodePort()).isGreaterThan(0);
  }
}
