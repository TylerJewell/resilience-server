package com.example.application;

import akka.Done;
import akka.javasdk.testkit.KeyValueEntityTestKit;
import com.example.domain.Greeting;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class GreetingEntityTest {

  @Test
  void shouldSetName() {
    var testKit = KeyValueEntityTestKit.of("greeting-1", GreetingEntity::new);
    var result = testKit.method(GreetingEntity::setName).invoke("Alice");
    assertThat(result.isReply()).isTrue();
    assertThat(result.getReply()).isEqualTo(Done.getInstance());
    assertThat(testKit.getState().name()).isEqualTo("Alice");
  }

  @Test
  void shouldRejectEmptyName() {
    var testKit = KeyValueEntityTestKit.of("greeting-2", GreetingEntity::new);
    var result = testKit.method(GreetingEntity::setName).invoke("");
    assertThat(result.isError()).isTrue();
  }

  @Test
  void shouldGetEmptyState() {
    var testKit = KeyValueEntityTestKit.of("greeting-3", GreetingEntity::new);
    var result = testKit.method(GreetingEntity::get).invoke();
    assertThat(result.isReply()).isTrue();
    assertThat(result.getReply()).isEqualTo(new Greeting(""));
  }

  @Test
  void shouldGetAfterSet() {
    var testKit = KeyValueEntityTestKit.of("greeting-4", GreetingEntity::new);
    testKit.method(GreetingEntity::setName).invoke("Bob");
    var result = testKit.method(GreetingEntity::get).invoke();
    assertThat(result.getReply().name()).isEqualTo("Bob");
  }
}
