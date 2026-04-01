package com.example.application;

import akka.Done;
import akka.javasdk.annotations.Component;
import akka.javasdk.keyvalueentity.KeyValueEntity;
import com.example.domain.Greeting;

@Component(id = "greeting")
public class GreetingEntity extends KeyValueEntity<Greeting> {

  @Override
  public Greeting emptyState() {
    return new Greeting("");
  }

  public Effect<Done> setName(String name) {
    if (name == null || name.isBlank()) {
      return effects().error("Name must not be empty");
    }
    var updated = currentState().withName(name);
    return effects().updateState(updated).thenReply(Done.getInstance());
  }

  public ReadOnlyEffect<Greeting> get() {
    return effects().reply(currentState());
  }
}
