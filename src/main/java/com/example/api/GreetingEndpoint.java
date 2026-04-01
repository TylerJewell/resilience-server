package com.example.api;

import akka.http.javadsl.model.HttpResponse;
import akka.javasdk.annotations.Acl;
import akka.javasdk.annotations.http.Get;
import akka.javasdk.annotations.http.HttpEndpoint;
import akka.javasdk.annotations.http.Put;
import akka.javasdk.client.ComponentClient;
import akka.javasdk.http.AbstractHttpEndpoint;
import akka.javasdk.http.HttpResponses;
import com.example.application.GreetingEntity;
import com.example.domain.Greeting;
import com.typesafe.config.Config;

@HttpEndpoint("/hello")
@Acl(allow = @Acl.Matcher(principal = Acl.Principal.ALL))
public class GreetingEndpoint extends AbstractHttpEndpoint {

  private final ComponentClient componentClient;
  private final int nodePort;

  public GreetingEndpoint(ComponentClient componentClient, Config config) {
    this.componentClient = componentClient;
    int basePort = config.getInt("akka.javasdk.dev-mode.http-port");
    int offset = config.hasPath("akka.runtime.dev-mode.http-port-offset")
        ? config.getInt("akka.runtime.dev-mode.http-port-offset")
        : 0;
    this.nodePort = basePort + offset;
  }

  public record SetNameRequest(String name) {}

  public record GreetingResponse(String id, String message, int nodePort) {}

  @Put("/{id}")
  public HttpResponse setName(String id, SetNameRequest request) {
    componentClient.forKeyValueEntity(id)
        .method(GreetingEntity::setName)
        .invoke(request.name());
    return HttpResponses.ok();
  }

  @Get("/{id}")
  public GreetingResponse get(String id) {
    Greeting greeting = componentClient.forKeyValueEntity(id)
        .method(GreetingEntity::get)
        .invoke();
    String name = greeting.name().isEmpty() ? "World" : greeting.name();
    return new GreetingResponse(id, "Hello, " + name + "!", nodePort);
  }
}
