def concurrency
  :shared
end

def register(params)
  @field = params["field"]
end

def compact(h)
  h.inject({}) do |result, (k, v)|
    case v
    when Hash
      c = compact(v)
      result[k] = c unless c.empty?
    when String
      result[k] = v unless (v.empty? || (v == "-") || (v == "(empty)"))
    when Array
      c = v.delete_if{|e| e.nil? || (e.is_a?(String) && (e.empty? || (e == "-") || (e == "(empty)")))}
      result[k] = c unless c.empty?
    when NilClass
      # nothing
    else
      result[k] = v
    end
    result
  end
end

def filter(event)
  _hashfield = event.get("#{@field}")
  if !_hashfield.nil? && _hashfield.is_a?(Hash) then
    event.set("#{@field}", compact(_hashfield.to_hash))
  end
  [event]
end

###############################################################################
# tests

test "remove field keys with nil values" do

  parameters do
    { "field" => "nested" }
  end

  in_event { { "name" => "eleanor rigby", "age" => 59, "nested" => { "foo" => 1, "bar" => nil, "blat" => "-", "blarg" => "(empty)", "biz" => "yo" }} }

  expect("return a single event") do |events|
    events.size == 1
  end

  expect("kept the [name] key") do |events|
    events.first.get("[name]") == "eleanor rigby"
  end

  expect("kept the [age] key") do |events|
    events.first.get("[age]") == 59
  end

  expect("kept the [nested][foo] key") do |events|
    events.first.get("[nested][foo]") == 1
  end

  expect("kept the [nested][biz] key") do |events|
    events.first.get("[nested][biz]") == "yo"
  end

  expect("remove the bar key") do |events|
    !events.first.include?("[nested][bar]")
  end

  expect("remove the blat key") do |events|
    !events.first.include?("[nested][blat]")
  end

  expect("remove the blarg key") do |events|
    !events.first.include?("[nested][blarg]")
  end

end


test "call on non-hash field type" do

  parameters do
    { "field" => "name" }
  end

  in_event { { "name" => "eleanor rigby", "age" => 59 } }

  expect("return a single event") do |events|
    events.size == 1
  end

  expect("kept the [name] key") do |events|
    events.first.get("[name]") == "eleanor rigby"
  end

  expect("kept the [age] key") do |events|
    events.first.get("[age]") == 59
  end

end